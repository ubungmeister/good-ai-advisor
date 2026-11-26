"""Read-only check that the demo policy can reach embedded VPP evidence."""

import os
import uuid

from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.policy import Policy
from app.models.user import User
from scripts.retrieval_scope import resolve_document_scope


def main():
    raw_user_id = os.getenv("SUPABASE_AUTH_USER_ID", "").strip()
    if raw_user_id:
        try:
            owner_filter = User.id == uuid.UUID(raw_user_id)
        except ValueError:
            raise ValueError("SUPABASE_AUTH_USER_ID must be a valid UUID.") from None
    else:
        email = os.getenv("SUPABASE_AUTH_USER_EMAIL", "test@example.com").strip()
        owner_filter = User.email == email

    with SessionLocal() as db:
        policy = db.scalar(select(Policy).join(User, User.id == Policy.owner_user_id).where(
            Policy.policy_number == "TI-2026-0001", owner_filter,
        ))
        if policy is None:
            raise ValueError("Demo policy missing. Run python -m scripts.seed_dev first.")
        document = resolve_document_scope(db, "VPP_CP_2021", policy.product_version_id)
        count = db.scalar(select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.embedding.is_not(None),
        ))
        print(f"PASS: demo policy has access to {count} embedded VPP chunks.")
        print("Copy these local demo values into server/.env before starting the API:")
        print(f"DEV_USER_ID={policy.owner_user_id}")
        print(f"DEV_POLICY_ID={policy.id}")
        print(f"Product version ID: {policy.product_version_id}")


if __name__ == "__main__":
    main()
