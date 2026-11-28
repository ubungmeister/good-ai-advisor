"""Fail-closed customer-facing eligibility for support procedures."""

from datetime import date

from app.schemas.support_knowledge import SupportProcedure


class SupportPublicationGate:
    def is_eligible(
        self,
        procedure: SupportProcedure,
        *,
        product_version: str,
        as_of: date,
    ) -> bool:
        if procedure.review_status != "APPROVED":
            return False
        if procedure.publication_status != "PUBLISHED":
            return False
        if not procedure.retrieval_eligible or not procedure.reviewed_by or not procedure.approved_at:
            return False
        if not procedure.sources or not procedure.source_ids:
            return False
        if not set(procedure.source_ids).issubset(
            {source.source_id for source in procedure.sources}
        ):
            return False
        if not (
            procedure.version_independent_approved
            or product_version in procedure.applicable_policy_versions
        ):
            return False
        if procedure.effective_from and as_of < procedure.effective_from:
            return False
        if procedure.effective_to and as_of > procedure.effective_to:
            return False
        return True
