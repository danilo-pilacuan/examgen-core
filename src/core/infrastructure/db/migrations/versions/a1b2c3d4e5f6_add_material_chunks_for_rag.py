"""add material_chunks for RAG

Revision ID: a1b2c3d4e5f6
Revises: 5230ab459f09
Create Date: 2026-08-11 06:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5230ab459f09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: añade tabla material_chunks para el RAG."""
    op.create_table('material_chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('subject_id', sa.UUID(), nullable=False),
    sa.Column('source_file', sa.String(length=500), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_material_chunks_subject_id', 'material_chunks', ['subject_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_material_chunks_subject_id', table_name='material_chunks')
    op.drop_table('material_chunks')
