from app.schemas.query_plan import EvidenceRoute, PlannedTask, TaskType
from app.schemas.task_routing import RoutedTask, TaskTarget


class TaskRouter:

    def route(
        self,
        *,
        task: PlannedTask,
    ) -> RoutedTask:

        if task.evidence_route is not None:
            return self._route_explicit(task)

        match task.type:

            case TaskType.PROCEDURE:
                targets = [
                    TaskTarget.SUPPORT,
                ]
                evidence_route = EvidenceRoute.SUPPORT

            case TaskType.GENERAL_QUESTION:
                targets = [
                    TaskTarget.POLICY,
                    TaskTarget.RETRIEVAL,
                    TaskTarget.SUPPORT,
                ]
                evidence_route = EvidenceRoute.BOTH

            case TaskType.POLICY_DETAILS:
                targets = [
                    TaskTarget.POLICY,
                ]
                evidence_route = EvidenceRoute.POLICY

            case TaskType.COVERAGE_CHECK:
                targets = [
                    TaskTarget.POLICY,
                    TaskTarget.RETRIEVAL,
                    TaskTarget.SUPPORT,
                ]
                evidence_route = EvidenceRoute.BOTH

            case _:
                raise ValueError(
                    f"Unsupported task type: {task.type}"
                )

        return RoutedTask(
            task=task,
            targets=targets,
            evidence_route=evidence_route,
        )

    @staticmethod
    def _route_explicit(task: PlannedTask) -> RoutedTask:
        route = task.evidence_route
        if task.type == TaskType.COVERAGE_CHECK and route in {
            EvidenceRoute.SUPPORT, EvidenceRoute.NONE,
        }:
            route = EvidenceRoute.BOTH
        if task.type == TaskType.POLICY_DETAILS and route in {
            EvidenceRoute.SUPPORT, EvidenceRoute.NONE,
        }:
            route = EvidenceRoute.POLICY
        if task.type == TaskType.POLICY_DETAILS:
            policy_targets = [TaskTarget.POLICY]
        elif task.type == TaskType.COVERAGE_CHECK:
            policy_targets = [TaskTarget.POLICY, TaskTarget.RETRIEVAL]
        else:
            policy_targets = [TaskTarget.RETRIEVAL]
        targets = {
            EvidenceRoute.POLICY: policy_targets,
            EvidenceRoute.SUPPORT: [TaskTarget.SUPPORT],
            EvidenceRoute.BOTH: [TaskTarget.POLICY, TaskTarget.RETRIEVAL, TaskTarget.SUPPORT],
            EvidenceRoute.NONE: [],
        }[route]
        return RoutedTask(task=task, targets=targets, evidence_route=route)
