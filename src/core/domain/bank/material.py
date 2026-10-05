"""Servicio para indexar material de una materia en la BD (RAG).

Reutiliza la lógica de extracción de texto y chunking del script
`scripts/index_material.py` y de los extractores de `src/agents/nodes.py`,
pero expuesta como funciones reutilizables para que tanto el script CLI como
las tools del agente conversacional puedan agregar material a una materia.

Este módulo NO escribe a través de SQL directo en el banco de preguntas, pero
sí inserta `MaterialChunk` (material de estudio, no preguntas), que es la
operación legítima de "agregar material a una materia".

Además de indexar el texto en la BD, permite GUARDAR el archivo físico en el
directorio de material de la materia (`data/inputs/<Materia>/...`) para que
quede como parte del repositorio de material (igual que los apuntes).
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

# Directorio raíz del material de las materias. Se resuelve por env var
# (MATERIAL_ROOT) o por defecto a `data/inputs` relativo a la raíz del repo.
DEFAULT_MATERIAL_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "inputs"


def material_root() -> Path:
    """Devuelve el directorio raíz del material (configurable por env)."""
    import os

    root = os.environ.get("MATERIAL_ROOT", "")
    return Path(root) if root else DEFAULT_MATERIAL_ROOT


def subject_folder_name(name: str) -> str:
    """Normaliza el nombre de una materia a un nombre de carpeta seguro.

    Ej: "Economía Aplicada" -> "Economia_Aplicada"
        "Inglés Técnico"    -> "Ingles_Tecnico"

    Elimina acentos, espacios -> guiones bajos, y caracteres no alfanuméricos.
    """
    # Normalizar Unicode y eliminar marcas de acentuación.
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Espacios y separadores -> guión bajo; quitar caracteres no seguros.
    text = re.sub(r"[\s]+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_\-.]", "", text)
    return text.strip("_")


def save_file_to_subject_folder(
    raw_bytes: bytes,
    filename: str,
    subject_name: str,
) -> Path:
    """Guarda el archivo físico en el directorio de material de la materia.

    Crea `data/inputs/<SubjectFolder>/<filename>` si no existe y copia los
    bytes del archivo. Devuelve la ruta guardada.

    Si el archivo ya existe, añade un sufijo numérico para no sobrescribirlo.
    """
    folder = material_root() / subject_folder_name(subject_name)
    folder.mkdir(parents=True, exist_ok=True)

    # Nombre de archivo seguro.
    safe_name = Path(filename).name or "archivo"
    dest = folder / safe_name
    # Evitar sobrescribir: añadir sufijo si ya existe.
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
    """Extrae el texto de un archivo según su extensión."""
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
        text: contenido del material (ya extraído).
        subject_id: id de la materia destino.
        source_label: etiqueta de origen (ej. nombre del archivo).
        clear_previous: si True, borra los chunks previos de esa fuente.

    Returns:
        dict con estadísticas (chunks_guardados, materia, etc.).
    """
    chunks = chunk_text(text)
    if not chunks:
        return {"chunks_guardados": 0, "mensaje": "No se pudo extraer texto del material."}

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
            return {"chunks_guardados": 0, "mensaje": f"No existe la materia {subject_id}"}

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
            "chunks_guardados": len(chunks),
            "materia": subject.name,
            "subject_id": str(subject.id),
            "fuente": source_label,
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
        return {"chunks_guardados": 0, "mensaje": f"No existe el archivo: {file_path}"}
    try:
        text = extract_file_text(file_path)
    except Exception as e:  # noqa: BLE001
        return {"chunks_guardados": 0, "mensaje": f"Error al extraer el archivo: {str(e)[:200]}"}
    return index_text_for_subject(
        text,
        subject_id,
        source_label=file_path.name,
        clear_previous=clear_previous,
    )
