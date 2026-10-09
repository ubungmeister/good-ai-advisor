from collections.abc import Sequence
from enum import Enum

from app.schemas.response_validation import GroundingFact
from app.schemas.task_result import (
    PolicyTaskContent,
    RetrievalTaskContent,
    TaskResult,
)
from app.schemas.task_routing import TaskTarget


class GroundingFactBuilder:
    """
    Converts trusted structured TaskResult objects
    into evidence that can be checked by Model B.

    This service:
    - does not call an LLM
    - does not query the database
    - does not interpret insurance meaning
    - does not inspect the generated answer
    """

    def build(
        self,
        *,
        task_results: Sequence[TaskResult],
    ) -> list[GroundingFact]:

        facts: dict[str, GroundingFact] = {}

        for result in task_results:

            if (
                    result.target == TaskTarget.POLICY
                    and isinstance(
                result.content,
                PolicyTaskContent,
            )
            ):
                self._add_policy_facts(
                    content=result.content,
                    facts=facts,
                )

            elif (
                    result.target == TaskTarget.RETRIEVAL
                    and isinstance(
                result.content,
                RetrievalTaskContent,
            )
            ):
                self._add_retrieval_facts(
                    content=result.content,
                    facts=facts,
                )

            else:
                raise ValueError(
                    "Invalid TaskResult target/content combination."
                )

        return list(facts.values())

    # ========================================================
    # POLICY
    # ========================================================

    def _add_policy_facts(
        self,
        *,
        content: PolicyTaskContent,
        facts: dict[str, GroundingFact],
    ) -> None:

        policy = content.policy
        policy_id = str(policy.id)

        self._add_fact(
            facts=facts,
            fact_id=(
                f"policy:{policy_id}:status"
            ),
            label="Policy status",
            value=policy.policy_status,
        )

        self._add_fact(
            facts=facts,
            fact_id=(
                f"policy:{policy_id}:payment_status"
            ),
            label="Payment status",
            value=policy.payment_status,
        )

        self._add_fact(
            facts=facts,
            fact_id=(
                f"policy:{policy_id}:start_date"
            ),
            label="Policy start date",
            value=policy.start_date,
        )

        self._add_fact(
            facts=facts,
            fact_id=(
                f"policy:{policy_id}:end_date"
            ),
            label="Policy end date",
            value=policy.end_date,
        )

        if policy.premium_amount is not None:

            premium = str(policy.premium_amount)

            if policy.currency:
                premium += f" {policy.currency}"

            self._put(
                facts=facts,
                fact=GroundingFact(
                    id=(
                        f"policy:{policy_id}:premium"
                    ),
                    text=(
                        f"Policy premium: {premium}"
                    ),
                ),
            )

        if policy.paid_at is not None:
            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:paid_at"
                ),
                label="Policy paid at",
                value=policy.paid_at,
            )

        # ----------------------------------------------------
        # COVERAGES
        # ----------------------------------------------------

        for coverage in content.coverages:

            text = (
                f"Coverage: "
                f"{coverage.coverage_type.name} "
                f"({coverage.coverage_type.code})"
            )

            if coverage.limit_amount is not None:

                text += (
                    f". Limit: "
                    f"{coverage.limit_amount}"
                )

                if coverage.currency:
                    text += f" {coverage.currency}"

            self._put(
                facts=facts,
                fact=GroundingFact(
                    id=(
                        "policy.coverage:"
                        f"{coverage.id}"
                    ),
                    text=text,
                ),
            )

        # ----------------------------------------------------
        # OPTIONS
        # ----------------------------------------------------

        for option in content.options:

            selected = (
                "selected"
                if option.selected
                else "not selected"
            )

            text = (
                f"Policy option: "
                f"{option.name} "
                f"({option.code}) "
                f"is {selected}."
            )

            if option.variant:
                text += (
                    f" Variant: {option.variant}."
                )

            self._put(
                facts=facts,
                fact=GroundingFact(
                    id=(
                        "policy.option:"
                        f"{option.id}"
                    ),
                    text=text,
                ),
            )

        # ----------------------------------------------------
        # PEOPLE
        # ----------------------------------------------------
        #
        # We deliberately do NOT send names to Model B here.
        # Roles are enough for the current grounding use case.
        # ----------------------------------------------------

        if content.people:

            roles = [
                self._display(person.role)
                for person in content.people
            ]

            self._put(
                facts=facts,
                fact=GroundingFact(
                    id=(
                        f"policy:{policy_id}:people_roles"
                    ),
                    text=(
                        "Policy person roles: "
                        + ", ".join(roles)
                    ),
                ),
            )

        # ----------------------------------------------------
        # TRAVEL DETAILS
        # ----------------------------------------------------

        travel = content.travel_details

        if travel is not None:

            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:"
                    "travel.coverage_mode"
                ),
                label="Travel coverage mode",
                value=travel.coverage_mode,
            )

            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:"
                    "travel.territory_type"
                ),
                label="Travel territory",
                value=travel.territory_type,
            )

            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:"
                    "travel.destination_country"
                ),
                label="Destination country",
                value=travel.destination_country,
            )

            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:"
                    "travel.trip_purpose"
                ),
                label="Trip purpose",
                value=travel.trip_purpose,
            )

            self._add_fact(
                facts=facts,
                fact_id=(
                    f"policy:{policy_id}:"
                    "travel.sport_level"
                ),
                label="Sport level",
                value=travel.sport_level,
            )

    # ========================================================
    # RETRIEVAL
    # ========================================================

    def _add_retrieval_facts(
        self,
        *,
        content: RetrievalTaskContent,
        facts: dict[str, GroundingFact],
    ) -> None:

        for chunk in content.chunks:

            text = chunk.content.strip()

            if not text:
                continue

            metadata: list[str] = []

            if chunk.section_title:
                metadata.append(
                    f"Section: {chunk.section_title}"
                )

            if chunk.article_number:
                metadata.append(
                    f"Article: {chunk.article_number}"
                )

            if chunk.page_number is not None:
                metadata.append(
                    f"Page: {chunk.page_number}"
                )

            if metadata:
                text = (
                    " | ".join(metadata)
                    + "\n"
                    + text
                )

            self._put(
                facts=facts,
                fact=GroundingFact(
                    id=(
                        "document.chunk:"
                        f"{chunk.id}"
                    ),
                    text=text,
                ),
            )

    # ========================================================
    # HELPERS
    # ========================================================

    def _add_fact(
        self,
        *,
        facts: dict[str, GroundingFact],
        fact_id: str,
        label: str,
        value: object | None,
    ) -> None:

        if value is None:
            return

        self._put(
            facts=facts,
            fact=GroundingFact(
                id=fact_id,
                text=(
                    f"{label}: "
                    f"{self._display(value)}"
                ),
            ),
        )

    def _put(
        self,
        *,
        facts: dict[str, GroundingFact],
        fact: GroundingFact,
    ) -> None:
        """
        Deduplicate evidence by stable evidence ID.

        The same policy may appear in more than one task.
        Model B should not receive duplicate facts.
        """

        facts[fact.id] = fact

    def _display(
        self,
        value: object,
    ) -> str:
        """
        Convert trusted scalar values into predictable
        text without interpreting their meaning.
        """

        if isinstance(value, Enum):
            return str(value.value)

        return str(value)