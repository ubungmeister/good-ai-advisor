import uuid

from pydantic import BaseModel, Field, model_validator

from app.schemas.policy import PolicyDetailsResponse
from app.schemas.query_plan import TaskType
from app.schemas.task_routing import TaskTarget
from app.schemas.support_knowledge import SupportDocumentItem, SupportStep, SupportSource


# ============================================================
# POLICY CONTENT
# ============================================================


class PolicyTaskContent(PolicyDetailsResponse):
    """
    Structured policy data returned by PolicyService
    and carried inside TaskResult.

    Inherits:

    policy
    coverages
    options
    people
    travel_details
    """

    pass


# ============================================================
# RETRIEVAL CONTENT
# ============================================================


class RetrievedChunk(BaseModel):
    """
    One document chunk returned by RetrievalService.
    """

    id: uuid.UUID
    document_id: uuid.UUID

    content: str = Field(
        min_length=1,
    )

    # This is the retrieval/reranker score.
    # It is NOT a probability.
    score: float

    page_number: int | None = None
    article_number: str | None = None
    section_title: str | None = None
    coverage_code: str | None = None


class RetrievalTaskContent(BaseModel):
    """
    Structured result of one RETRIEVAL target.
    """

    chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        max_length=10,
    )


class SupportEvidenceUnit(BaseModel):
    procedure_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    immediate_steps: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    recommended_documents: list[str] = Field(default_factory=list)
    applicability: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    escalation_guidance: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    coverage_considerations: list[str] = Field(default_factory=list)
    review_status: str | None = None
    steps: list[SupportStep] = Field(default_factory=list)
    sources: list[SupportSource] = Field(default_factory=list)
    police_involvement: object | None = None
    required_document_details: list[SupportDocumentItem] = Field(default_factory=list)
    recommended_document_details: list[SupportDocumentItem] = Field(default_factory=list)


class SupportTaskContent(BaseModel):
    units: list[SupportEvidenceUnit] = Field(default_factory=list, max_length=5)


# ============================================================
# TASK RESULT
# ============================================================


class TaskResult(BaseModel):
    """
    Normalized result produced by one routed task target.

    POLICY
        -> PolicyTaskContent

    RETRIEVAL
        -> RetrievalTaskContent
    """

    task_type: TaskType
    target: TaskTarget

    content: (
        PolicyTaskContent
        | RetrievalTaskContent
        | SupportTaskContent
    )

    @model_validator(mode="after")
    def validate_target_content(self):
        """
        Ensure target and content type agree.

        We do not want states such as:

        target = POLICY
        content = RetrievalTaskContent(...)
        """

        if (
            self.target == TaskTarget.POLICY
            and not isinstance(
                self.content,
                PolicyTaskContent,
            )
        ):
            raise ValueError(
                "POLICY target requires "
                "PolicyTaskContent."
            )

        if (
            self.target == TaskTarget.RETRIEVAL
            and not isinstance(
                self.content,
                RetrievalTaskContent,
            )
        ):
            raise ValueError(
                "RETRIEVAL target requires "
                "RetrievalTaskContent."
            )

        if (
            self.target == TaskTarget.SUPPORT
            and not isinstance(self.content, SupportTaskContent)
        ):
            raise ValueError(
                "SUPPORT target requires SupportTaskContent."
            )

        return self
