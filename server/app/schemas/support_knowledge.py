"""Validated domain models for the canonical support knowledge collection."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SupportSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(min_length=1)
    url: str | None = None
    section: str | None = None
    effective_from: date | None = None
    last_checked_at: date | None = None


class SupportStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=1)
    requirement_type: str
    evidence_level: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    condition: str | None = None


class SupportDocumentItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    requirement_type: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    condition: str | None = None


class SupportProcedure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    document_type: str
    schema_version: str
    language: str
    category: str
    title: str
    scenario: str
    intent_tag: str
    question_variations: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    immediate_steps: list[SupportStep] = Field(default_factory=list)
    required_documents: list[str | SupportDocumentItem] = Field(default_factory=list)
    recommended_documents: list[str | SupportDocumentItem] = Field(default_factory=list)
    police_involvement: object | None = None
    clarifying_questions: list[str] = Field(default_factory=list)
    coverage_considerations: list[str] = Field(default_factory=list)
    escalation_conditions: list[str] = Field(default_factory=list)
    open_questions_for_expert: list[str] = Field(default_factory=list)
    sources: list[SupportSource] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_level: str
    official_scenario_specific_evidence: bool
    procedure_completeness: str
    priority: str
    policy_version_check_required: bool
    applicable_policy_versions: list[str] = Field(default_factory=list)
    version_independent_approved: bool = False
    review_status: str
    reviewed_by: str | None = None
    last_verified_at: date | None = None
    last_public_source_checked_at: date | None = None
    approved_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    publication_status: str
    retrieval_eligible: bool
    notes_for_reviewer: str | None = None


class SupportKnowledgeCollection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str
    document_type: str
    language: str
    dataset_status: str
    generated_at: date
    title: str
    procedures: list[SupportProcedure]
