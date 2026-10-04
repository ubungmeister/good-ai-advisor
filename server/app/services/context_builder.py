from app.schemas.task_result import TaskResult
from app.schemas.task_routing import TaskTarget


class ContextBuilder:
    """
    Combines trusted task results into one context
    that can be sent to the final LLM.
    """

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

            task_content = (
                f"[TASK: {result.task_type.value}]\n"
                f"{result.content}"
            )

            if result.target == TaskTarget.POLICY:
                policy_parts.append(
                    task_content
                )

            elif result.target == TaskTarget.RETRIEVAL:
                retrieval_parts.append(
                    task_content
                )

            else:
                raise ValueError(
                    f"Unsupported task result target: "
                    f"{result.target}"
                )

        sections: list[str] = []

        if policy_parts:
            sections.append(
                "[POLICY FACTS]\n\n"
                + "\n\n".join(
                    policy_parts
                )
            )

        if retrieval_parts:
            sections.append(
                "[INSURANCE DOCUMENTATION]\n\n"
                + "\n\n".join(
                    retrieval_parts
                )
            )

        return "\n\n".join(
            sections
        )