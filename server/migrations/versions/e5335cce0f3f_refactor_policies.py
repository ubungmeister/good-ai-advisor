"""refactor policies

Revision ID: e5335cce0f3f
Revises: e9cfa6815835
Create Date: 2026-09-02 18:21:53.895117
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e5335cce0f3f"
down_revision: Union[str, Sequence[str], None] = "e9cfa6815835"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


policy_status_enum = postgresql.ENUM(
    "PENDING",
    "ACTIVE",
    "CANCELLED",
    "EXPIRED",
    name="policy_status",
    create_type=False,
)

payment_status_enum = postgresql.ENUM(
    "UNPAID",
    "PAID",
    "REFUNDED",
    "PARTIALLY_REFUNDED",
    name="payment_status",
    create_type=False,
)


def upgrade() -> None:
    # =====================================================
    # 1. CREATE ENUM TYPES
    # =====================================================

    bind = op.get_bind()

    postgresql.ENUM(
        "PENDING",
        "ACTIVE",
        "CANCELLED",
        "EXPIRED",
        name="policy_status",
    ).create(bind, checkfirst=True)

    postgresql.ENUM(
        "UNPAID",
        "PAID",
        "REFUNDED",
        "PARTIALLY_REFUNDED",
        name="payment_status",
    ).create(bind, checkfirst=True)

    # =====================================================
    # 2. ADD NEW POLICY COLUMNS
    # =====================================================

    op.add_column(
        "policies",
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            nullable=False,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "plan_id",
            sa.Uuid(),
            nullable=False,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "policy_status",
            policy_status_enum,
            nullable=False,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "payment_status",
            payment_status_enum,
            nullable=False,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "paid_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    # =====================================================
    # 3. CURRENCY MAY BE NULL ACCORDING TO ERD
    # =====================================================

    op.alter_column(
        "policies",
        "currency",
        existing_type=sa.String(length=3),
        nullable=True,
    )

    # =====================================================
    # 4. FOREIGN KEYS
    # =====================================================

    op.create_foreign_key(
        "fk_policies_owner_user_id_users",
        "policies",
        "users",
        ["owner_user_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_policies_plan_id_plans",
        "policies",
        "plans",
        ["plan_id"],
        ["id"],
    )

    # Old user_id FK is no longer needed
    op.drop_constraint(
        "policies_user_id_fkey",
        "policies",
        type_="foreignkey",
    )

    # =====================================================
    # 5. REMOVE OLD COLUMNS
    # =====================================================

    op.drop_column(
        "policies",
        "territory_code",
    )

    op.drop_column(
        "policies",
        "status",
    )

    op.drop_column(
        "policies",
        "user_id",
    )


def downgrade() -> None:
    # =====================================================
    # 1. RECREATE OLD COLUMNS AS NULLABLE TEMPORARILY
    # =====================================================

    op.add_column(
        "policies",
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "territory_code",
            sa.String(length=50),
            nullable=True,
        ),
    )

    # =====================================================
    # 2. COPY BACK WHAT WE CAN
    #
    # territory cannot really be reconstructed because
    # it was removed from Policy. For our synthetic test
    # project we use EUROPE.
    # =====================================================

    op.execute(
        """
        UPDATE policies
        SET
            user_id = owner_user_id,
            status = policy_status::text,
            territory_code = 'EUROPE',
            currency = COALESCE(currency, 'CZK')
        """
    )

    # Restore old NOT NULL constraints
    op.alter_column(
        "policies",
        "user_id",
        nullable=False,
    )

    op.alter_column(
        "policies",
        "status",
        nullable=False,
    )

    op.alter_column(
        "policies",
        "territory_code",
        nullable=False,
    )

    op.alter_column(
        "policies",
        "currency",
        existing_type=sa.String(length=3),
        nullable=False,
    )

    # =====================================================
    # 3. FOREIGN KEYS
    # =====================================================

    op.drop_constraint(
        "fk_policies_plan_id_plans",
        "policies",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_policies_owner_user_id_users",
        "policies",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "policies_user_id_fkey",
        "policies",
        "users",
        ["user_id"],
        ["id"],
    )

    # =====================================================
    # 4. REMOVE NEW COLUMNS
    # =====================================================

    op.drop_column("policies", "updated_at")
    op.drop_column("policies", "created_at")
    op.drop_column("policies", "paid_at")
    op.drop_column("policies", "payment_status")
    op.drop_column("policies", "policy_status")
    op.drop_column("policies", "plan_id")
    op.drop_column("policies", "owner_user_id")

    # =====================================================
    # 5. REMOVE ENUM TYPES
    # =====================================================

    bind = op.get_bind()

    payment_status_enum.drop(
        bind,
        checkfirst=True,
    )

    policy_status_enum.drop(
        bind,
        checkfirst=True,
    )