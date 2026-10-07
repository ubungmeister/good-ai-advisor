from app.schemas.task_result import (
    PolicyTaskContent,
    RetrievalTaskContent,
    TaskResult,
)
from app.schemas.task_routing import TaskTarget


class ContextBuilder:
    """
    Converts trusted structured TaskResult objects
    into one text context for the final answer LLM.

    It does NOT reason about insurance.
    It only formats trusted backend data.
    """

    def build(
        self,
        *,
        results: list[TaskResult],
    ) -> str:

        if not results:
            return ""

        sections: list[str] = []

        for result in results:

            if result.target == TaskTarget.POLICY:
                sections.append(
                    self._build_policy_context(
                        task_type=result.task_type.value,
                        content=result.content,
                    )
                )

            elif result.target == TaskTarget.RETRIEVAL:
                sections.append(
                    self._build_retrieval_context(
                        task_type=result.task_type.value,
                        content=result.content,
                    )
                )

            else:
                raise ValueError(
                    "Unsupported task result target: "
                    f"{result.target}"
                )

        return "\n\n".join(sections)

    # ========================================================
    # POLICY
    # ========================================================

    def _build_policy_context(
        self,
        *,
        task_type: str,
        content: PolicyTaskContent,
    ) -> str:

        policy = content.policy

        lines: list[str] = [
            "[POLICY FACTS]",
            f"[TASK: {task_type}]",
            "",
            f"Policy status: {policy.policy_status.value}",
            f"Payment status: {policy.payment_status.value}",
            f"Start date: {policy.start_date}",
            f"End date: {policy.end_date}",
        ]

        if policy.premium_amount is not None:
            premium = str(policy.premium_amount)

            if policy.currency:
                premium += f" {policy.currency}"

            lines.append(
                f"Premium amount: {premium}"
            )

        # ----------------------------------------------------
        # COVERAGES
        # ----------------------------------------------------

        if content.coverages:
            lines.append("")
            lines.append("Coverages:")

            for coverage in content.coverages:

                line = (
                    f"- {coverage.coverage_type.name} "
                    f"({coverage.coverage_type.code})"
                )

                if coverage.limit_amount is not None:
                    line += (
                        f", limit: "
                        f"{coverage.limit_amount}"
                    )

                    if coverage.currency:
                        line += f" {coverage.currency}"

                lines.append(line)

        # ----------------------------------------------------
        # OPTIONS
        # ----------------------------------------------------

        if content.options:
            lines.append("")
            lines.append("Policy options:")

            for option in content.options:

                selected = (
                    "selected"
                    if option.selected
                    else "not selected"
                )

                line = (
                    f"- {option.name} "
                    f"({option.code}): "
                    f"{selected}"
                )

                if option.variant:
                    line += (
                        f", variant: "
                        f"{option.variant}"
                    )

                lines.append(line)

        # ----------------------------------------------------
        # INSURED PEOPLE
        # ----------------------------------------------------

        if content.people:
            lines.append("")
            lines.append("Insured people:")

            for person_link in content.people:
                lines.append(
                    f"- role: {person_link.role}"
                )

        # ----------------------------------------------------
        # TRAVEL DETAILS
        # ----------------------------------------------------

        travel = content.travel_details

        if travel is not None:
            lines.append("")
            lines.append("Travel details:")

            lines.append(
                f"- coverage mode: "
                f"{travel.coverage_mode}"
            )

            lines.append(
                f"- territory type: "
                f"{travel.territory_type}"
            )

            if travel.destination_country:
                lines.append(
                    f"- destination country: "
                    f"{travel.destination_country}"
                )

            if travel.trip_purpose:
                lines.append(
                    f"- trip purpose: "
                    f"{travel.trip_purpose}"
                )

            if travel.sport_level:
                lines.append(
                    f"- sport level: "
                    f"{travel.sport_level}"
                )

        return "\n".join(lines)

    # ========================================================
    # RETRIEVAL
    # ========================================================

    def _build_retrieval_context(
        self,
        *,
        task_type: str,
        content: RetrievalTaskContent,
    ) -> str:

        lines: list[str] = [
            "[INSURANCE DOCUMENTATION]",
            f"[TASK: {task_type}]",
        ]

        for index, chunk in enumerate(
            content.chunks,
            start=1,
        ):
            lines.append("")
            lines.append(
                f"[DOCUMENT {index}]"
            )

            lines.append(
                f"Chunk ID: {chunk.id}"
            )

            if chunk.page_number is not None:
                lines.append(
                    f"Page: {chunk.page_number}"
                )

            if chunk.article_number:
                lines.append(
                    f"Article: {chunk.article_number}"
                )

            if chunk.section_title:
                lines.append(
                    f"Section: {chunk.section_title}"
                )

            if chunk.coverage_code:
                lines.append(
                    f"Coverage code: "
                    f"{chunk.coverage_code}"
                )

            lines.append("")
            lines.append(chunk.content)

        return "\n".join(lines)