"""create chat_threads table (DEC-004 option a)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-27

Server-side thread registry per user:
  - Fixes BUG-022: each thread records its owner (user_id); endpoints
    validate ownership instead of trusting any thread_id.
  - Fixes BUG-023: the conversation list comes from this table, so it
    survives browsers/devices (localStorage is no longer the source).
  - Badge metadata for the sidebar: last subject used and message count.
Existing checkpoint threads are adopted lazily: the first time an
authenticated user sends a message to a thread_id without a row, the row
is created for that user (checkpointer content is untouched).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_threads',
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('last_subject_id', sa.UUID(), nullable=True),
        sa.Column('last_subject_name', sa.String(length=200), nullable=True),
        sa.Column('message_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('thread_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['last_subject_id'], ['subjects.id']),
    )
    op.create_index('ix_chat_threads_user_id', 'chat_threads', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chat_threads_user_id', table_name='chat_threads')
    op.drop_table('chat_threads')
