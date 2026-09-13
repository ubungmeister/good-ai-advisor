"""set document chunk embedding dimension

Revision ID: d34034116022
Revises: 1260d031a66d
Create Date: 2026-09-13 16:58:17.198025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd34034116022'
down_revision: Union[str, Sequence[str], None] = '1260d031a66d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(384)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector
        """
    )