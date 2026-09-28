from app.schemas.request_analysis import (
    PlannedTask,
    RequestAnalysis,
)


class QueryPlanner:

    def get_tasks(
        self,
        *,
        analysis: RequestAnalysis,
    ) -> list[PlannedTask]:

        if not analysis.tasks:
            raise ValueError(
                "Request analysis must contain at least one task."
            )

        return analysis.tasks