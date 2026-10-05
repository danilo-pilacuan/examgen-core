"""add verification fields and full question structure

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-07

Agrega a `generated_questions`:
  - Estructura completa del ítem (question_type, options, expected_answer,
    solution_explanation, subtopic, points) para no perder información al persistir.
  - Campos de verificación humana e IA (verified_by_human, verified_by_ai,
    ai_review_notes, ai_review_priority).
  - Campos de procedencia/auditoría (source, created_by).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('generated_questions', sa.Column('question_type', sa.String(length=50), nullable=True))
    op.add_column('generated_questions', sa.Column('options', sa.JSON(), nullable=True))
    op.add_column('generated_questions', sa.Column('expected_answer', sa.Text(), nullable=True))
    op.add_column('generated_questions', sa.Column('solution_explanation', sa.Text(), nullable=True))
    op.add_column('generated_questions', sa.Column('subtopic', sa.String(length=200), nullable=True))
    op.add_column('generated_questions', sa.Column('points', sa.Float(), nullable=True))
    op.add_column('generated_questions', sa.Column('verified_by_human', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('generated_questions', sa.Column('verified_by_ai', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('generated_questions', sa.Column('ai_review_notes', sa.Text(), nullable=True))
    op.add_column('generated_questions', sa.Column('ai_review_priority', sa.String(length=20), nullable=True))
    op.add_column('generated_questions', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('generated_questions', sa.Column('created_by', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('generated_questions', 'created_by')
    op.drop_column('generated_questions', 'source')
    op.drop_column('generated_questions', 'ai_review_priority')
    op.drop_column('generated_questions', 'ai_review_notes')
    op.drop_column('generated_questions', 'verified_by_ai')
    op.drop_column('generated_questions', 'verified_by_human')
    op.drop_column('generated_questions', 'points')
    op.drop_column('generated_questions', 'subtopic')
    op.drop_column('generated_questions', 'solution_explanation')
    op.drop_column('generated_questions', 'expected_answer')
    op.drop_column('generated_questions', 'options')
    op.drop_column('generated_questions', 'question_type')
