"""add exams table and exam name

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-19

Persists every generated exam (professor request):
  - `exams` table: blueprint, items, artifact file names, ZIP, name.
  - `exams.name`: human-readable name requested by the professor (used
    for the artifact file names instead of a random hash).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # noqa: F401  (keeps the vector extension import consistent)

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'exams',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('blueprint', sa.JSON(), nullable=False),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('num_versions', sa.Integer(), server_default='1', nullable=False),
        sa.Column('pdf_paths', sa.JSON(), nullable=False),
        sa.Column('zip_path', sa.String(length=300), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name='fk_exams_subject_id'),
    )
    op.create_index('ix_exams_subject_id', 'exams', ['subject_id'])
    op.create_index('ix_exams_created_at', 'exams', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_exams_created_at', table_name='exams')
    op.drop_index('ix_exams_subject_id', table_name='exams')
    op.drop_table('exams')
