from enum import StrEnum

from pydantic import BaseModel

from app.schemas.query_plan import EvidenceRoute, PlannedTask


class TaskTarget(StrEnum):
    # TODO: Rename RETRIEVAL to DOCUMENTATION; update all callers and
    # serialized evaluation fixtures together. SUPPORT also retrieves data.
    RETRIEVAL = "RETRIEVAL"
    POLICY = "POLICY"
    SUPPORT = "SUPPORT"


class RoutedTask(BaseModel):
    task: PlannedTask
    targets: list[TaskTarget]
    evidence_route: EvidenceRoute
