"""Service layer de acceso al banco de preguntas.

TODAS las operaciones de escritura sobre `generated_questions` deben pasar
por este módulo. El agente NUNCA ejecuta SQL directo.

Reglas de seguridad (requisito de Felipe):
  - `create_question()`: el agente puede crear preguntas.
  - `update_question()` / `delete_question()`: BLOQUEADAS si la pregunta
    ya fue `verified_by_human=True` (una pregunta verificada por un humano
    no debe poder ser modificada por el agente).
  - `set_human_verification()`: SOLO la invoca el paso de confirmación
    humana explícito del chat (human-in-the-loop), nunca el agente autónomo.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.infrastructure.db.connection import SessionLocal
from core.domain.models import GeneratedQuestion


class SecurityError(Exception):
    """Se lanza cuando el agente intenta modificar/borrar una pregunta
    verificada por humano (o cualquier operación no permitida)."""


def _get_question(db: Session, question_id: str | uuid.UUID) -> GeneratedQuestion:
    qid = uuid.UUID(str(question_id))
    q = db.get(GeneratedQuestion, qid)
    if q is None:
        raise SecurityError(f"Pregunta no encontrada: {qid}")
    return q


def get_question(question_id: str | uuid.UUID, db: Session | None = None) -> GeneratedQuestion | None:
    """Lectura de una pregunta por id. Permite pasar una sesión propia."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        qid = uuid.UUID(str(question_id))
        return db.get(GeneratedQuestion, qid)
    finally:
        if own:
            db.close()


def list_questions(
    subject_id: str | uuid.UUID,
    verified_by_human: bool | None = None,
    verified_by_ai: bool | None = None,
    topic: str | None = None,
    limit: int = 50,
    db: Session | None = None,
) -> list[GeneratedQuestion]:
    """Lista preguntas del banco con filtros opcionales (para recuperar del
    banco sin generar nuevas)."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        stmt = select(GeneratedQuestion).where(
            GeneratedQuestion.subject_id == uuid.UUID(str(subject_id))
        )
        if verified_by_human is not None:
            stmt = stmt.where(GeneratedQuestion.verified_by_human == verified_by_human)
        if verified_by_ai is not None:
            stmt = stmt.where(GeneratedQuestion.verified_by_ai == verified_by_ai)
        if topic:
            stmt = stmt.where(GeneratedQuestion.topic == topic)
        stmt = stmt.order_by(GeneratedQuestion.created_at.desc()).limit(limit)
        return list(db.execute(stmt).scalars().all())
    finally:
        if own:
            db.close()


def create_question(
    subject_id: str | uuid.UUID,
    *,
    topic: str,
    bloom_level: str,
    difficulty: str,
    question_text: str,
    embedding: list[float],
    question_type: str | None = None,
    options: list[dict] | None = None,
    expected_answer: str | None = None,
    solution_explanation: str | None = None,
    subtopic: str | None = None,
    points: float | None = None,
    source: str = "generated",
    created_by: str = "agent",
    verified_by_ai: bool = False,
    ai_review_notes: str | None = None,
    ai_review_priority: str | None = None,
    db: Session | None = None,
) -> GeneratedQuestion:
    """Crea una pregunta. El agente puede crear; la verificación humana se
    marca después en `set_human_verification`."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = GeneratedQuestion(
            subject_id=uuid.UUID(str(subject_id)),
            topic=topic,
            bloom_level=bloom_level,
            difficulty=difficulty,
            question_text=question_text,
            embedding=embedding,
            question_type=question_type,
            options=options,
            expected_answer=expected_answer,
            solution_explanation=solution_explanation,
            subtopic=subtopic,
            points=points,
            source=source,
            created_by=created_by,
            verified_by_ai=verified_by_ai,
            ai_review_notes=ai_review_notes,
            ai_review_priority=ai_review_priority,
            verified_by_human=False,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        return q
    finally:
        if own:
            db.close()


def update_question(
    question_id: str | uuid.UUID,
    *,
    fields: dict[str, Any],
    db: Session | None = None,
) -> GeneratedQuestion:
    """Actualiza una pregunta.

    Seguridad: si `verified_by_human=True`, se lanza `SecurityError`. El
    agente no puede modificar preguntas verificadas por un humano.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = _get_question(db, question_id)
        if q.verified_by_human:
            raise SecurityError(
                f"La pregunta {q.id} está verificada por humano y no puede modificarse."
            )
        for key, value in fields.items():
            if not hasattr(q, key):
                raise SecurityError(f"Campo desconocido: {key}")
            setattr(q, key, value)
        db.commit()
        db.refresh(q)
        return q
    finally:
        if own:
            db.close()


def delete_question(question_id: str | uuid.UUID, db: Session | None = None) -> None:
    """Elimina una pregunta.

    Seguridad: si `verified_by_human=True`, se lanza `SecurityError`.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = _get_question(db, question_id)
        if q.verified_by_human:
            raise SecurityError(
                f"La pregunta {q.id} está verificada por humano y no puede eliminarse."
            )
        db.delete(q)
        db.commit()
    finally:
        if own:
            db.close()


def set_human_verification(
    question_id: str | uuid.UUID,
    verified: bool = True,
    db: Session | None = None,
) -> GeneratedQuestion:
    """Marca una pregunta como verificada por un humano.

    ⚠️ Este método SOLO debe invocarse desde el paso de confirmación humana
    explícito del chat (human-in-the-loop). El agente autónomo no lo llama.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = _get_question(db, question_id)
        q.verified_by_human = verified
        db.commit()
        db.refresh(q)
        return q
    finally:
        if own:
            db.close()
