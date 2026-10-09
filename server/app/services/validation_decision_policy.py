from collections.abc import Sequence

from app.schemas.response_validation import (
    GroundingCheckResult,
    GroundingVerdict,
    ValidationAction,
    ValidationIssue,
    ValidationIssueCode,
    ValidationResult,
)


class ValidationDecisionPolicy:
    """
    Deterministic backend decision policy.

    It does NOT perform semantic validation.

    It takes:
    - deterministic guard issues
    - Model B grounding result
    - regeneration count

    and decides:

    OK
    REGENERATE
    REJECT
    HANDOFF
    """

    MAX_REGENERATION_ATTEMPTS = 1

    def decide(
        self,
        *,
        grounding_result: GroundingCheckResult,
        guard_issues: Sequence[ValidationIssue],
        regeneration_count: int,
    ) -> ValidationResult:

        issues = list(guard_issues)

        # =====================================================
        # 1. INVALID REGENERATION STATE
        # =====================================================

        if regeneration_count < 0:
            issues.append(
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
            )

            return ValidationResult(
                action=ValidationAction.REJECT,
                grounding=grounding_result.verdict,
                issues=issues,
            )

        # =====================================================
        # 2. HARD RUNTIME FAILURES
        # =====================================================

        issue_codes = {
            issue.code
            for issue in issues
        }

        if (
            ValidationIssueCode.INVALID_RUNTIME_STATE
            in issue_codes
        ):
            return ValidationResult(
                action=ValidationAction.REJECT,
                grounding=grounding_result.verdict,
                issues=issues,
            )

        if (
            ValidationIssueCode.POLICY_FACT_MISMATCH
            in issue_codes
        ):
            return ValidationResult(
                action=ValidationAction.REJECT,
                grounding=grounding_result.verdict,
                issues=issues,
            )

        # =====================================================
        # 3. NO TRUSTED EVIDENCE
        # =====================================================

        if (
            ValidationIssueCode.NO_TRUSTED_EVIDENCE
            in issue_codes
        ):
            return ValidationResult(
                action=ValidationAction.HANDOFF,
                grounding=GroundingVerdict.NOT_CHECKED,
                issues=issues,
            )

        # =====================================================
        # 4. VALIDATOR FAILURE
        # =====================================================

        if (
            ValidationIssueCode.VALIDATOR_ERROR
            in issue_codes
        ):
            return ValidationResult(
                action=ValidationAction.HANDOFF,
                grounding=GroundingVerdict.NOT_CHECKED,
                issues=issues,
            )

        # =====================================================
        # 5. EMPTY ANSWER
        # =====================================================

        if (
            ValidationIssueCode.EMPTY_ANSWER
            in issue_codes
        ):
            if (
                regeneration_count
                < self.MAX_REGENERATION_ATTEMPTS
            ):
                return ValidationResult(
                    action=ValidationAction.REGENERATE,
                    grounding=GroundingVerdict.NOT_CHECKED,
                    issues=issues,
                )

            return ValidationResult(
                action=ValidationAction.HANDOFF,
                grounding=GroundingVerdict.NOT_CHECKED,
                issues=issues,
            )

        # =====================================================
        # 6. GROUNDING PASSED
        # =====================================================

        if (
            grounding_result.verdict
            == GroundingVerdict.SUPPORTED
        ):
            return ValidationResult(
                action=ValidationAction.OK,
                grounding=GroundingVerdict.SUPPORTED,
                issues=[],
            )

        # =====================================================
        # 7. GROUNDING FAILED
        # =====================================================

        grounding_issues = (
            self._build_grounding_issues(
                grounding_result
            )
        )

        issues.extend(
            grounding_issues
        )

        if grounding_result.verdict in {
            GroundingVerdict.UNSUPPORTED,
            GroundingVerdict.CONTRADICTED,
        }:

            if (
                regeneration_count
                < self.MAX_REGENERATION_ATTEMPTS
            ):
                return ValidationResult(
                    action=ValidationAction.REGENERATE,
                    grounding=grounding_result.verdict,
                    issues=issues,
                )

            return ValidationResult(
                action=ValidationAction.HANDOFF,
                grounding=grounding_result.verdict,
                issues=issues,
            )

        # =====================================================
        # 8. UNEXPECTED STATE
        # =====================================================

        issues.append(
            ValidationIssue(
                code=(
                    ValidationIssueCode
                    .INVALID_RUNTIME_STATE
                ),
                message=(
                    "Unexpected grounding verdict."
                ),
            )
        )

        return ValidationResult(
            action=ValidationAction.REJECT,
            grounding=grounding_result.verdict,
            issues=issues,
        )

    # ========================================================
    # GROUNDING -> VALIDATION ISSUES
    # ========================================================

    def _build_grounding_issues(
        self,
        result: GroundingCheckResult,
    ) -> list[ValidationIssue]:

        issues: list[ValidationIssue] = []

        if (
            result.verdict
            == GroundingVerdict.CONTRADICTED
        ):
            issue_code = (
                ValidationIssueCode
                .CONTRADICTED_CLAIM
            )

            message = (
                "Generated answer contains a claim "
                "that contradicts trusted evidence."
            )

        else:
            issue_code = (
                ValidationIssueCode
                .UNSUPPORTED_CLAIM
            )

            message = (
                "Generated answer contains a claim "
                "that is not supported by trusted "
                "evidence."
            )

        for claim in result.claims:

            if (
                not claim.grounding_required
                or claim.supported
            ):
                continue

            issues.append(
                ValidationIssue(
                    code=issue_code,
                    message=message,
                    claim=claim.claim,
                    evidence=claim.evidence_ids,
                )
            )

        return issues