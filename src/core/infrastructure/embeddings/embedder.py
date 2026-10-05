"""Configurable embeddings layer.

The pipeline uses embeddings for:
  1. Indexing a subject's material (RAG).
  2. Semantic similarity search in pgvector.
  3. Deduplication of generated items.

Embeddings are obtained from an OpenAI-compatible service running in local
Docker (projects/embedding-service) at http://localhost:8081/v1/embeddings.
"""
from typing import Protocol

import requests

from core.config import settings


class Embedder(Protocol):
    """Interface of an embeddings generator."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one vector per text."""
        ...


class RemoteEmbedder:
    """Gets embeddings from an OpenAI-compatible service (local Docker)."""

    def __init__(self, url: str = "", model: str = ""):
        self.url = url or settings.embedding_url
        self.model = model or settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = requests.post(
            self.url,
            json={"input": texts, "model": self.model},
            timeout=300,
        )
        resp.raise_for_status()
        payload = resp.json()
        # Sort by index to preserve the input order
        data = sorted(payload["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


def get_embedder() -> Embedder:
    """Returns the configured embedder (for now, always remote)."""
    return RemoteEmbedder()


# Reusable singleton instance
embedder = get_embedder()
