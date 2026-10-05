"""Rutas de salida compartidas (PDFs de exámenes, exportaciones CSV/XLSX).

El directorio de salida se comparte con el latex-compiler vía volumen y es
servido por exam-app en `GET /output/{filename}`.

Resolución (en orden):
  1. `EXAM_OUTPUT_DIR` (override explícito).
  2. `/app/output` (contenedor: volumen compartido con latex-compiler).
  3. `data/agent_outputs` relativo a la raíz del repo (desarrollo local).
"""
from __future__ import annotations

import os
from pathlib import Path


def _repo_root_candidates() -> list[Path]:
    """Raíces candidatas del repo (dev local), desde la ubicación de este archivo."""
    here = Path(__file__).resolve()
    return [p / "data" / "agent_outputs" for p in here.parents if (p / "data").exists()]


_CANDIDATE_OUTPUT = [
    Path("/app/output"),  # contenedor (volumen compartido con latex-compiler)
    *_repo_root_candidates(),  # desarrollo local (data/ existe en la raíz)
]


def get_output_dir() -> Path:
    """Devuelve el directorio de salida, creándolo si no existe."""
    env = os.environ.get("EXAM_OUTPUT_DIR", "")
    if env:
        out = Path(env)
    else:
        out = next((p for p in _CANDIDATE_OUTPUT if p.exists()), _CANDIDATE_OUTPUT[-1])
    out.mkdir(parents=True, exist_ok=True)
    return out
