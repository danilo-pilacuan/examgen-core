"""Capa de embeddings configurable.

El pipeline usa embeddings para:
  1. Indexar el material de una materia (RAG).
  2. Búsqueda por similitud semántica en pgvector.
  3. Deduplicación de ítems generados.

Los embeddings se obtienen de un servicio OpenAI-compatible que corre en
Docker local (projects/embedding-service) en http://localhost:8081/v1/embeddings.
"""
from typing import Protocol

import requests

from core.config import settings


class Embedder(Protocol):
    """Interfaz de un generador de embeddings."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector por cada texto."""
        ...


class RemoteEmbedder:
    """Obtiene embeddings de un servicio OpenAI-compatible (Docker local)."""

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
        # Ordenar por índice para mantener el orden de entrada
        data = sorted(payload["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


def get_embedder() -> Embedder:
    """Devuelve el embedder configurado (por ahora, siempre remoto)."""
    return RemoteEmbedder()


# Instancia singleton reutilizable
embedder = get_embedder()
