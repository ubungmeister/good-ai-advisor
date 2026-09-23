"""enable lexical search extensions

Revision ID: 7cc703df2f5b
Revises: d34034116022
Create Date: 2026-09-20 17:39:24.330576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cc703df2f5b'
down_revision: Union[str, Sequence[str], None] = 'd34034116022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS pg_trgm"
    )

    op.execute(
        "CREATE EXTENSION IF NOT EXISTS unaccent"
    )

def downgrade() -> None:
    """Downgrade schema."""
    pass
