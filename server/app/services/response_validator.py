from collections.abc import Sequence

from app.schemas.response_validation import (
    GroundingCheckResult,
    GroundingVerdict,
    ValidationIssue,
    ValidationIssueCode,
    ValidationResult,
)
from app.schemas.task_result import TaskResult

from app.services.deterministic_guard_service import (
    DeterministicGuardService,
)
from app.services.grounding_fact_builder import (
    GroundingFactBuilder,
)
from app.services.grounding_validator import (
    GroundingValidator,
)
from app.services.validation_decision_policy import (
    ValidationDecisionPolicy,
)


class ResponseValidator:
    """
    Orchestrates validation of Model A's draft answer.

    Flow:

    draft answer
        ↓
    deterministic guards
        ↓
    grounding facts
        ↓
    Model B grounding validation
        ↓
    deterministic decision policy
        ↓
    ValidationResult
    """

    def __init__(
        self,
        *,
        guard_service: DeterministicGuardService,
        grounding_fact_builder: GroundingFactBuilder,
        grounding_validator: GroundingValidator,
        decision_policy: ValidationDecisionPolicy,
    ):
        self.guard_service = guard_service
        self.grounding_fact_builder = (
            grounding_fact_builder
        )
        self.grounding_validator = (
            grounding_validator
        )
        self.decision_policy = decision_policy

    async def validate(
        self,
        *,
        question: str,
        draft_answer: str,
        task_results: Sequence[TaskResult],
        regeneration_count: int = 0,
    ) -> ValidationResult:

        # =====================================================
        # 1. DETERMINISTIC GUARDS
        # =====================================================

        guard_issues = self.guard_service.check(
            draft_answer=draft_answer,
            task_results=task_results,
            regeneration_count=regeneration_count,
        )

        print("\n--- RESPONSE VALIDATION ---")
        print("GUARD ISSUES:", guard_issues)

        # Some failures make semantic grounding either
        # impossible or unnecessary.
        if self._should_skip_grounding(
            issues=guard_issues,
        ):
            return self.decision_policy.decide(
                grounding_result=(
                    self._not_checked_result()
                ),
                guard_issues=guard_issues,
                regeneration_count=regeneration_count,
            )

        # =====================================================
        # 2. BUILD TRUSTED GROUNDING FACTS
        # =====================================================

        try:
            facts = self.grounding_fact_builder.build(
                task_results=task_results,
            )

        except Exception as exc:
            issues = list(guard_issues)

            issues.append(
                ValidationIssue(
                    code=(
                        ValidationIssueCode
                        .INVALID_RUNTIME_STATE
                    ),
                    message=(
                        "Failed to build trusted "
                        "grounding facts."
                    ),
                )
            )

            print(
                "GROUNDING FACT BUILDER ERROR:",
                repr(exc),
            )

            return self.decision_policy.decide(
                grounding_result=(
                    self._not_checked_result()
                ),
                guard_issues=issues,
                regeneration_count=regeneration_count,
            )

        print(
            "GROUNDING FACTS:",
            [
                fact.id
                for fact in facts
            ],
        )

        # TaskResult[] may technically exist while producing
        # no usable grounding facts.
        if not facts:
            issues = list(guard_issues)

            issues.append(
                ValidationIssue(
                    code=(
                        ValidationIssueCode
                        .NO_TRUSTED_EVIDENCE
                    ),
                    message=(
                        "No trusted grounding facts "
                        "were produced."
                    ),
                )
            )

            return self.decision_policy.decide(
                grounding_result=(
                    self._not_checked_result()
                ),
                guard_issues=issues,
                regeneration_count=regeneration_count,
            )

        # =====================================================
        # 3. SEMANTIC GROUNDING — MODEL B
        # =====================================================

        try:
            grounding_result = (
                await self.grounding_validator.validate(
                    question=question,
                    draft_answer=draft_answer,
                    facts=facts,
                )
            )

        except Exception as exc:
            issues = list(guard_issues)

            issues.append(
                ValidationIssue(
                    code=(
                        ValidationIssueCode
                        .VALIDATOR_ERROR
                    ),
                    message=(
                        "Semantic grounding validation "
                        "could not be completed."
                    ),
                )
            )

            print(
                "GROUNDING VALIDATOR ERROR:",
                repr(exc),
            )

            return self.decision_policy.decide(
                grounding_result=(
                    self._not_checked_result()
                ),
                guard_issues=issues,
                regeneration_count=regeneration_count,
            )

        print(
            "GROUNDING VERDICT:",
            grounding_result.verdict,
        )

        print(
            "GROUNDING CLAIMS:",
            grounding_result.claims,
        )

        # =====================================================
        # 4. FINAL BACKEND DECISION
        # =====================================================

        validation_result = (
            self.decision_policy.decide(
                grounding_result=grounding_result,
                guard_issues=guard_issues,
                regeneration_count=regeneration_count,
            )
        )

        print(
            "VALIDATION ACTION:",
            validation_result.action,
        )

        print(
            "VALIDATION ISSUES:",
            validation_result.issues,
        )

        return validation_result

    # ========================================================
    # HELPERS
    # ========================================================

    def _should_skip_grounding(
        self,
        *,
        issues: Sequence[ValidationIssue],
    ) -> bool:
        """
        Grounding should not run when the runtime is already
        in a state where Model B cannot meaningfully validate
        the answer.
        """

        blocking_codes = {
            ValidationIssueCode.EMPTY_ANSWER,
            ValidationIssueCode.NO_TRUSTED_EVIDENCE,
            ValidationIssueCode.INVALID_RUNTIME_STATE,
            ValidationIssueCode.POLICY_FACT_MISMATCH,
            (
                ValidationIssueCode
                .REGENERATION_LIMIT_EXCEEDED
            ),
        }

        return any(
            issue.code in blocking_codes
            for issue in issues
        )

    def _not_checked_result(
        self,
    ) -> GroundingCheckResult:
        """
        Backend-created state.

        Model B itself is not allowed to return NOT_CHECKED.
        """

        return GroundingCheckResult(
            verdict=GroundingVerdict.NOT_CHECKED,
            support_score=None,
            claims=[],
        )