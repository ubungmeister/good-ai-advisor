from collections.abc import Sequence

from app.schemas.response_validation import (
    ValidationIssue,
    ValidationIssueCode,
)


class DeterministicGuardService:
    """
    Runs hard backend validation checks that do not
    require semantic language understanding.

    This service does NOT decide whether the answer
    should be released, regenerated or handed off.

    It only reports deterministic validation issues.
    """

    MAX_REGENERATION_ATTEMPTS = 1

    def check(
        self,
        *,
        draft_answer: str,
        task_results: Sequence[object],
        regeneration_count: int = 0,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        issues.extend(
            self._check_answer_not_empty(
                    draft_answer=draft_answer,
            )
        )

        issues.extend(
            self._check_trusted_evidence_exists(
                task_results=task_results,
            )
        )

        issues.extend(
            self._check_regeneration_count(
                regeneration_count=regeneration_count,
            )
        )

        return issues

    # ========================================================
    # ANSWER CHECK
    # ========================================================

    def _check_answer_not_empty(
        self,
        *,
        draft_answer: str,
    ) -> list[ValidationIssue]:
        """
        Model A must return a non-empty answer.
        """

        if draft_answer.strip():
            return []

        return [
            ValidationIssue(
                code=ValidationIssueCode.EMPTY_ANSWER,
                message=(
                    "The generated answer is empty."
                ),
            )
        ]

    # ========================================================
    # TRUSTED EVIDENCE CHECK
    # ========================================================

    def _check_trusted_evidence_exists(
        self,
        *,
        task_results: Sequence[object],
    ) -> list[ValidationIssue]:
        """
        Normal insurance answers must have trusted
        service results available for validation.
        """

        if task_results:
            return []

        return [
            ValidationIssue(
                code=(
                    ValidationIssueCode
                    .NO_TRUSTED_EVIDENCE
                ),
                message=(
                    "No trusted task results are available "
                    "for validating the generated answer."
                ),
            )
        ]

    # ========================================================
    # REGENERATION LIMIT
    # ========================================================

    def _check_regeneration_count(
        self,
        *,
        regeneration_count: int,
    ) -> list[ValidationIssue]:
        """
        Prevent invalid retry states.

        One regeneration is allowed:

        initial generation:
            regeneration_count = 0

        regenerated answer:
            regeneration_count = 1
        """

        if regeneration_count < 0:
            return [
                ValidationIssue(
                    code=(
                        ValidationIssueCode
                        .INVALID_RUNTIME_STATE
                    ),
                    message=(
                        "Regeneration count cannot "
                        "be negative."
                    ),
                )
            ]

        if (
            regeneration_count
            <= self.MAX_REGENERATION_ATTEMPTS
        ):
            return []

        return [
            ValidationIssue(
                code=(
                    ValidationIssueCode
                    .REGENERATION_LIMIT_EXCEEDED
                ),
                message=(
                    "Maximum regeneration attempts "
                    "have been exceeded."
                ),
            )
        ]