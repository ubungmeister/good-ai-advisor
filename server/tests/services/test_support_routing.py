from app.schemas.query_plan import EvidenceRoute, PlannedTask, TaskType
from app.schemas.task_routing import TaskTarget
from app.services.task_router import TaskRouter


def planned_task(task_type: TaskType) -> PlannedTask:
    return PlannedTask(
        type=task_type,
        query="Jak nahlásit ztracené zavazadlo?",
        evidence="How do I report lost baggage?",
    )


def test_procedure_routes_to_support_evidence():
    routed = TaskRouter().route(task=planned_task(TaskType.PROCEDURE))

    assert routed.evidence_route == EvidenceRoute.SUPPORT
    assert routed.targets == [TaskTarget.SUPPORT]


def test_explicit_none_route_has_no_evidence_targets():
    routed = TaskRouter().route(
        task=planned_task(TaskType.GENERAL_QUESTION).model_copy(
            update={"evidence_route": EvidenceRoute.NONE}
        )
    )

    assert routed.evidence_route == EvidenceRoute.NONE
    assert routed.targets == []


def test_coverage_policy_route_still_fetches_customer_policy_and_terms():
    task = planned_task(TaskType.COVERAGE_CHECK).model_copy(
        update={"evidence_route": EvidenceRoute.POLICY}
    )
    routed = TaskRouter().route(task=task)
    assert routed.targets == [TaskTarget.POLICY, TaskTarget.RETRIEVAL]


def test_coverage_support_only_route_is_upgraded_to_both():
    task = planned_task(TaskType.COVERAGE_CHECK).model_copy(
        update={"evidence_route": EvidenceRoute.SUPPORT}
    )
    routed = TaskRouter().route(task=task)
    assert routed.evidence_route == EvidenceRoute.BOTH
    assert routed.targets == [TaskTarget.POLICY, TaskTarget.RETRIEVAL, TaskTarget.SUPPORT]


def test_policy_details_never_omit_customer_policy():
    task = planned_task(TaskType.POLICY_DETAILS).model_copy(
        update={"evidence_route": EvidenceRoute.SUPPORT}
    )
    routed = TaskRouter().route(task=task)
    assert routed.evidence_route == EvidenceRoute.POLICY
    assert routed.targets == [TaskTarget.POLICY]
