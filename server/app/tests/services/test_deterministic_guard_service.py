from app.schemas.response_validation import ValidationIssueCode
from app.services.deterministic_guard_service import (
    DeterministicGuardService,
)


def test_valid_runtime_state_has_no_issues():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="Your policy expires on 15 September 2026.",
        task_results=[object()],
        regeneration_count=0,
    )

    assert issues == []


def test_empty_answer_is_rejected():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="",
        task_results=[object()],
        regeneration_count=0,
    )

    codes = [issue.code for issue in issues]

    assert ValidationIssueCode.EMPTY_ANSWER in codes


def test_missing_trusted_evidence_is_detected():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="Some answer.",
        task_results=[],
        regeneration_count=0,
    )

    codes = [issue.code for issue in issues]

    assert ValidationIssueCode.NO_TRUSTED_EVIDENCE in codes


def test_negative_regeneration_count_is_invalid():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="Some answer.",
        task_results=[object()],
        regeneration_count=-1,
    )

    codes = [issue.code for issue in issues]

    assert ValidationIssueCode.INVALID_RUNTIME_STATE in codes


def test_one_regeneration_is_allowed():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="Some answer.",
        task_results=[object()],
        regeneration_count=1,
    )

    assert issues == []


def test_second_regeneration_exceeds_limit():
    service = DeterministicGuardService()

    issues = service.check(
        draft_answer="Some answer.",
        task_results=[object()],
        regeneration_count=2,
    )

    codes = [issue.code for issue in issues]

    assert (
        ValidationIssueCode.REGENERATION_LIMIT_EXCEEDED
        in codes
    )