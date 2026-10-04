from app.schemas.query_plan import (
    PlannedTask,
    QueryPlan,
    TaskType,
)


class TaskPrioritizer:

    _PRIORITY = {
        TaskType.PROCEDURE: 1,
        TaskType.COVERAGE_CHECK: 2,
        TaskType.POLICY_DETAILS: 3,
        TaskType.GENERAL_QUESTION: 4,
    }

    def prioritize(
        self,
        *,
        plan: QueryPlan,
    ) -> list[PlannedTask]:

        return sorted(
            plan.tasks,
            key=lambda task: self._PRIORITY[task.type],
        )