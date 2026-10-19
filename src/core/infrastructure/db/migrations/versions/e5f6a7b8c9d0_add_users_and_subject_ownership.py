"""add users and subject ownership

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-18

Adds the multi-tenant auth schema:
  - `users` table (professor accounts: email, name, password_hash, role).
  - `subjects.owner_id` (nullable FK to users.id). NULL = legacy/shared
    subject, visible to every professor (backward compatible).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # noqa: F401  (keeps the vector extension import consistent)

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('password_hash', sa.String(length=500), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='professor', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.add_column('subjects', sa.Column('owner_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_subjects_owner_id_users', 'subjects', 'users', ['owner_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_subjects_owner_id_users', 'subjects', type_='foreignkey')
    op.drop_column('subjects', 'owner_id')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
