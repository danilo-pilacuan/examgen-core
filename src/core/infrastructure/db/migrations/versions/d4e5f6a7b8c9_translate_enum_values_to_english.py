"""translate enum values and AI review priority to english

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-05

Translates persisted enum values in `generated_questions` to the new
English contract (stage 7 of the i18n plan). The Spanish values below are
the OLD data values being migrated (they must stay as-is to match the
existing rows):
  - bloom_level: recordar→remember, comprender→understand, aplicar→apply,
    analizar→analyze, evaluar→evaluate, crear→create
  - difficulty: facil→easy, medio→medium, dificil→hard
  - question_type: opcion_multiple→multiple_choice, verdadero_falso→true_false,
    respuesta_corta→short_answer, desarrollo→essay, relleno→fill_in_blank,
    todas_correctas→select_all
  - ai_review_priority: alta→high, media→medium, baja→low

Run ONLY against the local database (never remote servers).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BLOOM_MAP = [
    # (old Spanish value in DB, new English value) — data migration, not code
    ('recordar', 'remember'),
    ('comprender', 'understand'),
    ('aplicar', 'apply'),
    ('analizar', 'analyze'),
    ('evaluar', 'evaluate'),
    ('crear', 'create'),
]

_DIFFICULTY_MAP = [
    ('facil', 'easy'),
    ('medio', 'medium'),
    ('dificil', 'hard'),
]

_QUESTION_TYPE_MAP = [
    ('opcion_multiple', 'multiple_choice'),
    ('verdadero_falso', 'true_false'),
    ('respuesta_corta', 'short_answer'),
    ('desarrollo', 'essay'),
    ('relleno', 'fill_in_blank'),
    ('todas_correctas', 'select_all'),
]

_PRIORITY_MAP = [
    ('alta', 'high'),
    ('media', 'medium'),
    ('baja', 'low'),
]


def _translate(table: str, column: str, mapping: list[tuple[str, str]]) -> None:
    for old, new in mapping:
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = :new WHERE {column} = :old"
            ).bindparams(new=new, old=old)
        )


def upgrade() -> None:
    """Upgrade schema (translate persisted values)."""
    _translate('generated_questions', 'bloom_level', _BLOOM_MAP)
    _translate('generated_questions', 'difficulty', _DIFFICULTY_MAP)
    _translate('generated_questions', 'question_type', _QUESTION_TYPE_MAP)
    _translate('generated_questions', 'ai_review_priority', _PRIORITY_MAP)


def downgrade() -> None:
    """Downgrade schema (restore the old Spanish data values)."""
    _translate('generated_questions', 'bloom_level', [(n, o) for o, n in _BLOOM_MAP])
    _translate('generated_questions', 'difficulty', [(n, o) for o, n in _DIFFICULTY_MAP])
    _translate('generated_questions', 'question_type', [(n, o) for o, n in _QUESTION_TYPE_MAP])
    _translate('generated_questions', 'ai_review_priority', [(n, o) for o, n in _PRIORITY_MAP])
