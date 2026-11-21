"""Strict inputs for the small, versioned AI benchmark."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    suite: Literal["chat", "validator"]
    category: str = Field(min_length=1)
    question: str = Field(min_length=1)
    history: list[str] = Field(default_factory=list, max_length=4)
    use_policy: bool = True
    articles: list[int] = Field(default_factory=list)
    expected_behavior: Literal["answer", "clarify", "handoff", "critical"] = "answer"
    rubric: list[str] = Field(min_length=1)
    draft: str | None = None
    expected_accept: bool | None = None
    regeneration_count: int = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def check_suite(self):
        if self.suite == "validator":
            if self.draft is None or self.expected_accept is None or self.history:
                raise ValueError("Validator cases need a draft and acceptance label, without history")
        elif self.draft is not None or self.expected_accept is not None:
            raise ValueError("Chat cases cannot contain validator labels")
        return self


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    document_code: str
    label_status: str
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate evaluation case ID")
        return self
