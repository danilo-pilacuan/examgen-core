"""Service layer for question bank access.

ALL write operations on `generated_questions` must go through this module.
The agent NEVER executes direct SQL.

Security rules (Felipe's requirement):
  - `create_question()`: the agent can create questions.
  - `update_question()` / `delete_question()`: BLOCKED if the question is
    already `verified_by_human=True` (a human-verified question must not be
    modifiable by the agent).
  - `set_human_verification()`: ONLY invoked by the explicit human
    confirmation step of the chat (human-in-the-loop), never by the
    autonomous agent.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.infrastructure.db.connection import SessionLocal
from core.domain.models import GeneratedQuestion


class SecurityError(Exception):
    """Raised when the agent tries to modify/delete a human-verified question
    (or any other non-permitted operation)."""


def _get_question(db: Session, question_id: str | uuid.UUID) -> GeneratedQuestion:
    qid = uuid.UUID(str(question_id))
    q = db.get(GeneratedQuestion, qid)
    if q is None:
        raise SecurityError(f"Question not found: {qid}")
    return q


def get_question(question_id: str | uuid.UUID, db: Session | None = None) -> GeneratedQuestion | None:
    """Reads a question by id. Allows passing an own session."""
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
    """Lists bank questions with optional filters (to retrieve from the bank
    without generating new ones)."""
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
    """Creates a question. The agent can create; human verification is
    set later in `set_human_verification`."""
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
    """Updates a question.

    Security: if `verified_by_human=True`, raises `SecurityError`. The
    agent cannot modify human-verified questions.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = _get_question(db, question_id)
        if q.verified_by_human:
            raise SecurityError(
                f"Question {q.id} is verified by human and cannot be modified."
            )
        for key, value in fields.items():
            if not hasattr(q, key):
                raise SecurityError(f"Unknown field: {key}")
            setattr(q, key, value)
        db.commit()
        db.refresh(q)
        return q
    finally:
        if own:
            db.close()


def delete_question(question_id: str | uuid.UUID, db: Session | None = None) -> None:
    """Deletes a question.

    Security: if `verified_by_human=True`, raises `SecurityError`.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q = _get_question(db, question_id)
        if q.verified_by_human:
            raise SecurityError(
                f"Question {q.id} is verified by human and cannot be deleted."
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
    """Marks a question as verified by a human.

    ⚠️ This method must ONLY be invoked from the explicit human confirmation
    step of the chat (human-in-the-loop). The autonomous agent does not call it.
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
