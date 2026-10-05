"""ajustar embeddings a 1024 (bge-m3)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: cambia las columnas embedding a vector(1024) (bge-m3)."""
    op.alter_column(
        'generated_questions',
        'embedding',
        existing_type=pgvector.sqlalchemy.VECTOR(dim=1536),
        type_=pgvector.sqlalchemy.VECTOR(dim=1024),
        existing_nullable=False,
    )
    op.alter_column(
        'material_chunks',
        'embedding',
        existing_type=pgvector.sqlalchemy.VECTOR(dim=1536),
        type_=pgvector.sqlalchemy.VECTOR(dim=1024),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'generated_questions',
        'embedding',
        existing_type=pgvector.sqlalchemy.VECTOR(dim=1024),
        type_=pgvector.sqlalchemy.VECTOR(dim=1536),
        existing_nullable=False,
    )
    op.alter_column(
        'material_chunks',
        'embedding',
        existing_type=pgvector.sqlalchemy.VECTOR(dim=1024),
        type_=pgvector.sqlalchemy.VECTOR(dim=1536),
        existing_nullable=False,
    )
