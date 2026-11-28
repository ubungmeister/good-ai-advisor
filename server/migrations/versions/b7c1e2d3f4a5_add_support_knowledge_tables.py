"""add isolated support knowledge tables

Revision ID: b7c1e2d3f4a5
Revises: 7cc703df2f5b
"""

from typing import Sequence, Union

import pgvector
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7c1e2d3f4a5"
down_revision: Union[str, Sequence[str], None] = "7cc703df2f5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    publication_status = postgresql.ENUM(
        "REVIEW_ONLY", "PUBLISHED", "SUSPENDED",
        name="support_publication_status",
        create_type=False,
    )
    publication_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "support_knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("publication_status", publication_status, nullable=False),
        sa.Column("review_status", sa.String(length=50), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("applicable_product_versions", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("retrieval_eligible", sa.Boolean(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_id"),
    )
    op.create_table(
        "support_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("searchable_text", sa.Text(), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["support_knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_support_chunks_document_index"),
    )


def downgrade() -> None:
    op.drop_table("support_knowledge_chunks")
    op.drop_table("support_knowledge_documents")
    postgresql.ENUM(name="support_publication_status").drop(
        op.get_bind(), checkfirst=True
    )
