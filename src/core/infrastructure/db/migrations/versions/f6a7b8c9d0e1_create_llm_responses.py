"""create llm_responses audit table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-19

Adds the LLM raw audit table (second project review requirement):
  - One row per LLM call: serialized prompt, raw answer and (optionally)
    the raw chain of thought (`LLM_CAPTURE_THINKING=true`).
  - `context` identifies the caller (chat:model, pipeline:generator, ...).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # noqa: F401  (keeps the vector extension import consistent)

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'llm_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('thread_id', sa.String(length=100), nullable=True),
        sa.Column('context', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=200), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('raw_answer', sa.Text(), nullable=False),
        sa.Column('raw_thinking', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_responses_thread_id', 'llm_responses', ['thread_id'])
    op.create_index('ix_llm_responses_created_at', 'llm_responses', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_llm_responses_created_at', table_name='llm_responses')
    op.drop_index('ix_llm_responses_thread_id', table_name='llm_responses')
    op.drop_table('llm_responses')
