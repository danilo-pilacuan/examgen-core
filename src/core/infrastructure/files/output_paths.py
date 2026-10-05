"""Shared output paths (exam PDFs, CSV/XLSX exports).

The output directory is shared with the latex-compiler via a volume and is
served by exam-app at `GET /output/{filename}`.

Resolution (in order):
  1. `EXAM_OUTPUT_DIR` (explicit override).
  2. `/app/output` (container: shared volume with latex-compiler).
  3. `data/agent_outputs` relative to the repo root (local development).
"""
from __future__ import annotations

import os
from pathlib import Path


def _repo_root_candidates() -> list[Path]:
    """Candidate repo roots (local dev), from this file's location."""
    here = Path(__file__).resolve()
    return [p / "data" / "agent_outputs" for p in here.parents if (p / "data").exists()]


_CANDIDATE_OUTPUT = [
    Path("/app/output"),  # container (shared volume with latex-compiler)
    *_repo_root_candidates(),  # local development (data/ exists at the root)
]


def get_output_dir() -> Path:
    """Returns the output directory, creating it if it doesn't exist."""
    env = os.environ.get("EXAM_OUTPUT_DIR", "")
    if env:
        out = Path(env)
    else:
        out = next((p for p in _CANDIDATE_OUTPUT if p.exists()), _CANDIDATE_OUTPUT[-1])
    out.mkdir(parents=True, exist_ok=True)
    return out
