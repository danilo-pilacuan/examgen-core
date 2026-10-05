"""Service for indexing subject material into the DB (RAG).

Reuses the text-extraction and chunking logic of the `scripts/index_material.py`
script and the extractors from `src/agents/nodes.py`, exposed as reusable
functions so that both the CLI script and the conversational agent's tools can
add material to a subject.

This module does NOT write to the question bank via direct SQL, but it does
insert `MaterialChunk` (study material, not questions), which is the
legitimate "add material to a subject" operation.

Besides indexing text into the DB, it allows SAVING the physical file into
the subject's material directory (`data/inputs/<Subject>/...`) so it remains
part of the material repository (like the notes).
"""
from __future__ import annotations

import re
import shutil
import unicodedata
import uuid
from pathlib import Path

from core.infrastructure.db.connection import SessionLocal
from core.domain.models import Subject, MaterialChunk
from core.infrastructure.embeddings.embedder import embedder
from core.infrastructure.files.extract import (
    _extract_pdf,
    _extract_docx,
    _extract_pptx,
    _extract_xlsx,
    _extract_text_file,
)

CHUNK_SIZE = 1500   # caracteres por chunk
CHUNK_OVERLAP = 150  # solapamiento para no cortar ideas

# Root directory of the subjects' material. Resolved by env var
# (MATERIAL_ROOT) or defaults to `data/inputs` relative to the repo root.
DEFAULT_MATERIAL_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "inputs"


def material_root() -> Path:
    """Returns the material root directory (configurable by env)."""
    import os

    root = os.environ.get("MATERIAL_ROOT", "")
    return Path(root) if root else DEFAULT_MATERIAL_ROOT


def subject_folder_name(name: str) -> str:
    """Normalizes a subject name into a safe folder name.

    Example: "Applied Economics" -> "Applied_Economics"

    Removes accents, spaces -> underscores, and non-alphanumeric characters.
    """
    # Normalize Unicode and remove accent marks.
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Spaces and separators -> underscore; remove unsafe characters.
    text = re.sub(r"[\s]+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_\-.]", "", text)
    return text.strip("_")


def save_file_to_subject_folder(
    raw_bytes: bytes,
    filename: str,
    subject_name: str,
) -> Path:
    """Saves the physical file in the subject's material directory.

    Creates `data/inputs/<SubjectFolder>/<filename>` if it doesn't exist and
    copies the file bytes. Returns the saved path.

    If the file already exists, adds a numeric suffix to avoid overwriting.
    """
    folder = material_root() / subject_folder_name(subject_name)
    folder.mkdir(parents=True, exist_ok=True)

    # Nombre de archivo seguro.
    safe_name = Path(filename).name or "archivo"
    dest = folder / safe_name
    # Avoid overwriting: add a suffix if it already exists.
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        i = 1
        while dest.exists():
            dest = folder / f"{stem}_{i}{suffix}"
            i += 1

    dest.write_bytes(raw_bytes)
    return dest


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide un texto en chunks con solapamiento."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]


def extract_file_text(path: str | Path) -> str:
    """Extracts the text of a file according to its extension."""
    path = str(path)
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    if ext == "pdf":
        return _extract_pdf(path)
    if ext == "docx":
        return _extract_docx(path)
    if ext == "pptx":
        return _extract_pptx(path)
    if ext == "xlsx":
        return _extract_xlsx(path)
    return _extract_text_file(path)


def get_or_create_subject(name: str, subject_id: str | None = None) -> Subject:
    """Obtiene una materia por id/name, o la crea si no existe."""
    db = SessionLocal()
    try:
        if subject_id:
            subject = db.get(Subject, uuid.UUID(subject_id))
            if subject is not None:
                return subject
        subject = db.query(Subject).filter(Subject.name == name).first()
        if subject is not None:
            return subject
        subject = Subject(name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return subject
    finally:
        db.close()


def index_text_for_subject(
    text: str,
    subject_id: str,
    source_label: str,
    clear_previous: bool = False,
) -> dict:
    """Indexa un texto (material) en `material_chunks` de una materia.

    Args:
        text: material content (already extracted).
        subject_id: id de la materia destino.
        source_label: etiqueta de origen (ej. nombre del archivo).
        clear_previous: si True, borra los chunks previos de esa fuente.

    Returns:
        dict with stats (chunks_saved, subject, etc.).
    """
    chunks = chunk_text(text)
    if not chunks:
        return {"chunks_saved": 0, "message": "Could not extract text from the material."}

    # Generar embeddings en lotes.
    vectors: list[list[float]] = []
    batch = 16
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        vectors.extend(embedder.embed(part))

    db = SessionLocal()
    try:
        subject = db.get(Subject, uuid.UUID(subject_id))
        if subject is None:
            return {"chunks_saved": 0, "message": f"Subject {subject_id} does not exist"}

        if clear_previous:
            db.query(MaterialChunk).filter(
                MaterialChunk.subject_id == subject.id,
                MaterialChunk.source_file == source_label,
            ).delete()

        for idx, (content, vec) in enumerate(zip(chunks, vectors)):
            db.add(MaterialChunk(
                subject_id=subject.id,
                source_file=source_label,
                chunk_index=idx,
                content=content,
                embedding=vec,
            ))
        db.commit()
        return {
            "chunks_saved": len(chunks),
            "subject": subject.name,
            "subject_id": str(subject.id),
            "source": source_label,
        }
    finally:
        db.close()


def index_file_for_subject(
    file_path: str | Path,
    subject_id: str,
    clear_previous: bool = False,
) -> dict:
    """Extrae e indexa un archivo local en la materia destino."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {"chunks_saved": 0, "message": f"File does not exist: {file_path}"}
    try:
        text = extract_file_text(file_path)
    except Exception as e:  # noqa: BLE001
        return {"chunks_saved": 0, "message": f"Error extracting the file: {str(e)[:200]}"}
    return index_text_for_subject(
        text,
        subject_id,
        source_label=file_path.name,
        clear_previous=clear_previous,
    )
