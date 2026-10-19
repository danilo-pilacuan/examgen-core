"""Service layer for deleting indexed material.

ALL deletion of `MaterialChunk` rows (and the physical files behind them)
must go through this module, so the REST endpoint and the conversational
agent's tool share the exact same behavior (no duplicated SQL).

Deletion scope:
  - by `source_file`: removes every chunk indexed from that source and,
    optionally, the physical file in the subject's material folder.
  - `delete_all`: removes every chunk of the subject (physical files are
    kept unless `delete_physical_files=True`).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.domain.models import MaterialChunk, Subject
from core.domain.bank.material import material_root, subject_folder_name
from core.infrastructure.db.connection import SessionLocal


def _physical_path_for(subject: Subject, source_file: str) -> Path | None:
    """Resolves the physical file of a source inside the subject's folder.

    Returns None when the source is not a plain file name (e.g. an absolute
    path from a batch indexing run) or when it would escape the subject's
    folder (path traversal guard).
    """
    name = Path(source_file).name
    if not name or name in (".", ".."):
        return None
    folder = material_root() / subject_folder_name(subject.name)
    candidate = (folder / name).resolve()
    try:
        candidate.relative_to(folder.resolve())
    except ValueError:
        return None
    return candidate


def delete_source_file(
    subject_id: str | uuid.UUID,
    source_file: str,
    delete_physical_file: bool = True,
    db: Session | None = None,
) -> dict:
    """Deletes every chunk of one source file (and optionally the file).

    Returns a dict with the deleted chunk count and what happened to the
    physical file (`deleted` / `not_found` / `kept` / `unresolved`).
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        subject = db.get(Subject, uuid.UUID(str(subject_id)))
        if subject is None:
            raise ValueError(f"Subject {subject_id} does not exist")

        chunks = list(db.execute(
            select(MaterialChunk).where(
                MaterialChunk.subject_id == subject.id,
                MaterialChunk.source_file == source_file,
            )
        ).scalars().all())
        for chunk in chunks:
            db.delete(chunk)
        db.commit()

        physical_status = "unresolved"
        physical_path = _physical_path_for(subject, source_file)
        if physical_path is not None:
            if delete_physical_file:
                if physical_path.exists():
                    physical_path.unlink()
                    physical_status = "deleted"
                else:
                    physical_status = "not_found"
            else:
                physical_status = "kept"

        return {
            "subject": subject.name,
            "subject_id": str(subject.id),
            "source_file": source_file,
            "deleted_chunks": len(chunks),
            "physical_file": physical_status,
        }
    finally:
        if own:
            db.close()


def delete_all_material(
    subject_id: str | uuid.UUID,
    delete_physical_files: bool = False,
    db: Session | None = None,
) -> dict:
    """Deletes every indexed chunk of a subject (optionally its files)."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        subject = db.get(Subject, uuid.UUID(str(subject_id)))
        if subject is None:
            raise ValueError(f"Subject {subject_id} does not exist")

        chunks = list(db.execute(
            select(MaterialChunk).where(MaterialChunk.subject_id == subject.id)
        ).scalars().all())
        sources = {c.source_file for c in chunks}
        for chunk in chunks:
            db.delete(chunk)
        db.commit()

        deleted_files = 0
        if delete_physical_files:
            for source in sources:
                path = _physical_path_for(subject, source)
                if path is not None and path.exists():
                    path.unlink()
                    deleted_files += 1

        return {
            "subject": subject.name,
            "subject_id": str(subject.id),
            "deleted_chunks": len(chunks),
            "deleted_files": deleted_files,
        }
    finally:
        if own:
            db.close()
