from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.models.support_knowledge_document import SupportKnowledgeChunk, SupportKnowledgeDocument
from app.repositories.support_knowledge_repository import SupportKnowledgeRepository
from app.services.support_knowledge_loader import SupportKnowledgeLoader
from app.services.support_publication import SupportPublicationGate
from app.services.support_retrieval import SupportRetrievalService
from scripts.ingest_support_knowledge import ingest


CORPUS = Path(__file__).resolve().parents[2] / "data/knowledge/support/processed"


class FakeEmbeddings:
    def count_document_tokens(self, text):
        return len(text.split()) + 3

    def embed_documents(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]

    def embed_query(self, text):
        return [1.0] + [0.0] * 383


def test_all_json_files_are_embedded_and_saved_as_complete_procedures():
    db = Mock()
    db.scalar.return_value = None

    def set_id():
        db.add.call_args.args[0].id = uuid4()

    db.flush.side_effect = set_id
    count = ingest(CORPUS, db=db, embedding_service=FakeEmbeddings())

    documents = [call.args[0] for call in db.add.call_args_list
                 if isinstance(call.args[0], SupportKnowledgeDocument)]
    chunks = [call.args[0] for call in db.add.call_args_list
              if isinstance(call.args[0], SupportKnowledgeChunk)]
    assert count == len(documents) == 148
    assert len(chunks) >= count
    assert all(len(chunk.embedding) == 384 for chunk in chunks)
    assert all(document.document_metadata["procedure"]["immediate_steps"] is not None
               for document in documents)
    assert {chunk.document_id for chunk in chunks} == {document.id for document in documents}
    db.commit.assert_called_once()


def test_database_search_uses_draft_procedure_in_internal_prototype():
    procedure = SupportKnowledgeLoader().load_directory(CORPUS).procedures[0]
    document = SimpleNamespace(document_metadata={"procedure": procedure.model_dump(mode="json")})
    repository = Mock(spec=SupportKnowledgeRepository)
    repository.search_semantic.return_value = [document]
    repository.search_lexical.return_value = [document]
    service = SupportRetrievalService(
        publication_gate=SupportPublicationGate(), repository=repository,
        embedding_service=FakeEmbeddings(), include_drafts=True,
    )
    result = service.search(
        db=Mock(), question=procedure.title, product_version="2026.1",
        as_of=procedure.last_public_source_checked_at, limit=1,
    )
    assert not result.is_miss
    assert result.units[0].procedure_id == procedure.id
    assert result.units[0].steps
    assert result.units[0].review_status == "DRAFT"


def test_czech_query_expansion_keeps_the_original_question():
    expanded = SupportRetrievalService.expand_czech_query("Ztratil se mi kufr")
    assert expanded.startswith("Ztratil se mi kufr")
    assert "zavazadlo" in expanded
