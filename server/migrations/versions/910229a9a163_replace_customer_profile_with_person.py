"""replace customer profile with person

Revision ID: 910229a9a163
Revises: cafbc6e67f93
Create Date: 2026-08-30 17:51:48.726206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '910229a9a163'
down_revision: Union[str, Sequence[str], None] = 'cafbc6e67f93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create the new persons table
    op.create_table(
        "persons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("birth_number", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Add person_id temporarily as nullable.
    # Existing users do not have a person_id yet.
    op.add_column(
        "users",
        sa.Column("person_id", sa.Uuid(), nullable=True),
    )

    # This is another new field in our User model.
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 3. Copy existing customer profile data into persons.
    #
    # We reuse customer_profiles.user_id as persons.id.
    op.execute(
        """
        INSERT INTO persons (
            id,
            first_name,
            last_name,
            date_of_birth,
            birth_number,
            phone,
            created_at,
            updated_at
        )
        SELECT
            user_id,
            first_name,
            last_name,
            date_of_birth,
            birth_number,
            phone,
            CURRENT_TIMESTAMP,
            NULL
        FROM customer_profiles
        """
    )

    # 4. Connect every existing User with the newly created Person.
    op.execute(
        """
        UPDATE users
        SET person_id = customer_profiles.user_id
        FROM customer_profiles
        WHERE users.id = customer_profiles.user_id
        """
    )

    # 5. Now that existing users have person_id,
    # make the column mandatory.
    op.alter_column(
        "users",
        "person_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    # 6. One Person can have at most one User account.
    op.create_unique_constraint(
        "uq_users_person_id",
        "users",
        ["person_id"],
    )

    # 7. Add DB foreign key.
    op.create_foreign_key(
        "fk_users_person_id_persons",
        "users",
        "persons",
        ["person_id"],
        ["id"],
    )

    # 8. Old table is no longer needed.
    op.drop_table("customer_profiles")

def downgrade() -> None:
    """Downgrade schema."""

    # 1. Recreate the old customer_profiles table
    op.create_table(
        "customer_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("birth_number", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # 2. Copy Person data back into customer_profiles
    op.execute(
        """
        INSERT INTO customer_profiles (
            user_id,
            first_name,
            last_name,
            date_of_birth,
            birth_number,
            phone
        )
        SELECT
            users.id,
            persons.first_name,
            persons.last_name,
            persons.date_of_birth,
            persons.birth_number,
            persons.phone
        FROM users
        JOIN persons
            ON users.person_id = persons.id
        """
    )

    # 3. Remove User → Person constraints
    op.drop_constraint(
        "fk_users_person_id_persons",
        "users",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_users_person_id",
        "users",
        type_="unique",
    )

    # 4. Remove new User columns
    op.drop_column("users", "person_id")
    op.drop_column("users", "updated_at")

    # 5. Remove persons table
    op.drop_table("persons")