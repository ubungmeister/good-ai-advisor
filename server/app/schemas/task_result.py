import uuid

from pydantic import BaseModel, Field, model_validator

from app.schemas.policy import PolicyDetailsResponse
from app.schemas.query_plan import TaskType
from app.schemas.task_routing import TaskTarget


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

        return self