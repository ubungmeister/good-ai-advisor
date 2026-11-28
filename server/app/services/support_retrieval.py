"""Independent retrieval for the support collection."""

import re
from datetime import date
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from app.schemas.support_knowledge import SupportProcedure
from app.schemas.task_result import SupportEvidenceUnit
from app.services.support_publication import SupportPublicationGate
from app.repositories.support_knowledge_repository import SupportKnowledgeRepository
from app.services.embedding_service import EmbeddingService


class SupportRetrievalResult(BaseModel):
    units: list[SupportEvidenceUnit] = Field(default_factory=list, max_length=5)
    is_miss: bool
    attempted_query: str


class SupportRetrievalService:
    _REWRITE_STOPWORDS = {"jak", "co", "kdy", "kde", "mám", "mam", "prosím", "prosim", "se", "si", "mohu", "můžu"}
    _CZECH_ALIASES = {
        "kufr": "zavazadlo",
        "kufru": "zavazadla",
        "zavazadlo": "kufr",
        "zavazadla": "kufru",
        "zpožděné": "opožděné",
        "opožděné": "zpožděné",
        "doklad": "potvrzení",
        "účtenky": "doklady",
    }

    def __init__(
        self,
        *,
        procedures: list[SupportProcedure] | None = None,
        publication_gate: SupportPublicationGate,
        repository: SupportKnowledgeRepository | None = None,
        embedding_service: EmbeddingService | None = None,
        include_drafts: bool = False,
    ):
        self.procedures = procedures
        self.publication_gate = publication_gate
        self.repository = repository
        self.embedding_service = embedding_service
        self.include_drafts = include_drafts

    def search(
        self,
        *,
        question: str,
        product_version: str,
        as_of: date,
        limit: int = 5,
        db: Session | None = None,
    ) -> SupportRetrievalResult:
        if self.repository is not None:
            if db is None or self.embedding_service is None:
                raise ValueError("Database support retrieval needs a session and embedding service")
            semantic = self.repository.search_semantic(
                db, self.embedding_service.embed_query(question)
            )
            lexical = self.repository.search_lexical(db, question)
            expanded_question = self.expand_czech_query(question)
            expanded_lexical = (
                self.repository.search_lexical(db, expanded_question)
                if expanded_question != question else []
            )
            ranks: dict[str, tuple[float, SupportProcedure]] = {}
            for results in (semantic, lexical, expanded_lexical):
                seen_in_lane: set[str] = set()
                for rank, document in enumerate(results, start=1):
                    raw = (document.document_metadata or {}).get("procedure")
                    if raw is None:
                        continue
                    procedure = SupportProcedure.model_validate(raw)
                    if procedure.id in seen_in_lane:
                        continue
                    seen_in_lane.add(procedure.id)
                    if not self._eligible(procedure, product_version, as_of):
                        continue
                    current_score = ranks.get(procedure.id, (0.0, procedure))[0]
                    ranks[procedure.id] = (current_score + 1 / (20 + rank), procedure)
            ordered = sorted(ranks.values(), key=lambda item: item[0], reverse=True)
            units = [self._to_evidence_unit(procedure) for _, procedure in ordered[:limit]]
            return SupportRetrievalResult(
                units=units, is_miss=not units, attempted_query=question,
            )

        query_terms = self._terms(question)
        ranked: list[tuple[int, SupportProcedure]] = []

        for procedure in self.procedures or []:
            if not self._eligible(procedure, product_version, as_of):
                continue

            searchable = " ".join([
                procedure.title,
                procedure.scenario,
                procedure.intent_tag,
                *procedure.question_variations,
                *procedure.conditions,
            ])
            score = len(query_terms & self._terms(searchable))
            if score:
                ranked.append((score, procedure))

        ranked.sort(key=lambda item: item[0], reverse=True)
        units = [self._to_evidence_unit(procedure) for _, procedure in ranked[:limit]]
        return SupportRetrievalResult(
            units=units,
            is_miss=not units,
            attempted_query=question,
        )

    def _eligible(self, procedure: SupportProcedure, product_version: str, as_of: date) -> bool:
        if self.include_drafts:
            return True
        return self.publication_gate.is_eligible(
            procedure, product_version=product_version, as_of=as_of,
        )

    @classmethod
    def rewrite_query(cls, question: str) -> str:
        """One conservative retry that retains the user's content words."""
        terms = re.findall(r"\w+", question.casefold())
        rewritten = " ".join(
            term for term in terms
            if len(term) > 2 and term not in cls._REWRITE_STOPWORDS
        )
        return rewritten if rewritten and rewritten != question.casefold().strip() else question

    @classmethod
    def expand_czech_query(cls, question: str) -> str:
        terms = re.findall(r"\w+", question.casefold())
        aliases = [cls._CZECH_ALIASES[term] for term in terms if term in cls._CZECH_ALIASES]
        return question + " " + " ".join(aliases) if aliases else question

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {
            term
            for term in re.findall(r"[\wÀ-ž]+", value.casefold())
            if len(term) > 2
        }

    @staticmethod
    def _to_evidence_unit(procedure: SupportProcedure) -> SupportEvidenceUnit:
        return SupportEvidenceUnit(
            procedure_id=procedure.id,
            title=procedure.title,
            scenario=procedure.scenario,
            conditions=procedure.conditions,
            immediate_steps=[step.text for step in procedure.immediate_steps],
            required_documents=[item if isinstance(item, str) else item.name for item in procedure.required_documents],
            recommended_documents=[item if isinstance(item, str) else item.name for item in procedure.recommended_documents],
            applicability=procedure.applicable_policy_versions,
            provenance=procedure.source_ids,
            escalation_guidance=procedure.escalation_conditions,
            clarifying_questions=procedure.clarifying_questions,
            coverage_considerations=procedure.coverage_considerations,
            review_status=procedure.review_status,
            steps=procedure.immediate_steps,
            sources=procedure.sources,
            police_involvement=procedure.police_involvement,
            required_document_details=[item for item in procedure.required_documents if not isinstance(item, str)],
            recommended_document_details=[item for item in procedure.recommended_documents if not isinstance(item, str)],
        )
