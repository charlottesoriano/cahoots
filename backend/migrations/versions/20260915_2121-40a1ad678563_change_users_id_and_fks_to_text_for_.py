"""change users.id and FKs to text for clerk ids

Revision ID: 40a1ad678563
Revises: 218ce2d09b92
Create Date: 2026-09-15 21:21:39.366748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '40a1ad678563'
down_revision: Union[str, Sequence[str], None] = '218ce2d09b92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, fk constraint name, existing_nullable)
FK_COLUMNS = [
    ("availability_slots", "user_id", "availability_slots_user_id_fkey", False),
    ("event_invites", "created_by", "event_invites_created_by_fkey", False),
    ("event_members", "user_id", "event_members_user_id_fkey", False),
    ("events", "created_by", "events_created_by_fkey", False),
    ("expense_shares", "user_id", "expense_shares_user_id_fkey", False),
    ("expenses", "paid_by", "expenses_paid_by_fkey", False),
    ("itinerary_comments", "user_id", "itinerary_comments_user_id_fkey", False),
    ("itinerary_items", "created_by", "itinerary_items_created_by_fkey", False),
    ("notification_log", "user_id", "notification_log_user_id_fkey", False),
    ("packing_items", "assigned_to", "packing_items_assigned_to_fkey", True),
    ("poll_votes", "user_id", "poll_votes_user_id_fkey", False),
    ("polls", "created_by", "polls_created_by_fkey", False),
]


def upgrade() -> None:
    """Upgrade schema."""
    # FK constraints require both sides to share a type, so every constraint
    # touching users.id has to come off before either side's type changes.
    for _table, _column, fk_name, _nullable in FK_COLUMNS:
        op.drop_constraint(fk_name, _table, type_="foreignkey")

    op.alter_column('users', 'id',
               existing_type=sa.UUID(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=False)

    for table, column, _fk_name, nullable in FK_COLUMNS:
        op.alter_column(table, column,
                   existing_type=sa.UUID(),
                   type_=sqlmodel.sql.sqltypes.AutoString(),
                   existing_nullable=nullable)

    for table, column, fk_name, _nullable in FK_COLUMNS:
        op.create_foreign_key(fk_name, table, 'users', [column], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    for _table, _column, fk_name, _nullable in FK_COLUMNS:
        op.drop_constraint(fk_name, _table, type_="foreignkey")

    op.alter_column('users', 'id',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=sa.UUID(),
               existing_nullable=False,
               postgresql_using='id::uuid')

    for table, column, _fk_name, nullable in FK_COLUMNS:
        op.alter_column(table, column,
                   existing_type=sqlmodel.sql.sqltypes.AutoString(),
                   type_=sa.UUID(),
                   existing_nullable=nullable,
                   postgresql_using=f'{column}::uuid')

    for table, column, fk_name, _nullable in FK_COLUMNS:
        op.create_foreign_key(fk_name, table, 'users', [column], ['id'])
