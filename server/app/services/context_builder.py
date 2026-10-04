from app.schemas.task_result import TaskResult
from app.schemas.task_routing import TaskTarget


class ContextBuilder:

    def build(
        self,
        *,
        results: list[TaskResult],
    ) -> str:

        if not results:
            return ""

        policy_parts: list[str] = []
        retrieval_parts: list[str] = []

        for result in results:

            if result.target == TaskTarget.POLICY:
                policy_parts.append(result.content)

            elif result.target == TaskTarget.RETRIEVAL:
                retrieval_parts.append(result.content)

        sections: list[str] = []

        if policy_parts:
            sections.append(
                "[POLICY FACTS]\n"
                + "\n\n".join(policy_parts)
            )

        if retrieval_parts:
            sections.append(
                "[INSURANCE DOCUMENTATION]\n"
                + "\n\n".join(retrieval_parts)
            )

        return "\n\n".join(sections)