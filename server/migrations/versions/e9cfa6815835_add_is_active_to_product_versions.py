"""add is active to product versions

Revision ID: e9cfa6815835
Revises: 5f2532777ed8
Create Date: 2026-09-01 22:01:44.094752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9cfa6815835'
down_revision: Union[str, Sequence[str], None] = '5f2532777ed8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. is_active
    # Existing ProductVersion rows become active.
    op.add_column(
        "product_versions",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # 2. created_at
    # CURRENT_TIMESTAMP fills existing rows
    # and allows us to add the NOT NULL column safely.
    op.add_column(
        "product_versions",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # We only needed this DB default to migrate old rows.
    # New ORM objects already get created_at from the Python model.
    op.alter_column(
        "product_versions",
        "created_at",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "product_versions",
        "created_at",
    )

    op.drop_column(
        "product_versions",
        "is_active",
    )