from app.schemas.query_plan import PlannedTask, TaskType
from app.schemas.task_routing import RoutedTask, TaskTarget


class TaskRouter:

    def route(
        self,
        *,
        task: PlannedTask,
    ) -> RoutedTask:

        match task.type:

            case TaskType.PROCEDURE:
                targets = [
                    TaskTarget.RETRIEVAL,
                ]

            case TaskType.GENERAL_QUESTION:
                targets = [
                    TaskTarget.RETRIEVAL,
                ]

            case TaskType.POLICY_DETAILS:
                targets = [
                    TaskTarget.POLICY,
                ]

            case TaskType.COVERAGE_CHECK:
                targets = [
                    TaskTarget.POLICY,
                    TaskTarget.RETRIEVAL,
                ]

            case _:
                raise ValueError(
                    f"Unsupported task type: {task.type}"
                )

        return RoutedTask(
            task=task,
            targets=targets,
        )