"""Local ONNX embeddings via fastembed: no API key, no GPU, same vectors in dev, CI, and prod."""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from fastembed import TextEmbedding


class Embedder(Protocol):
    dimensions: int

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, dimensions: int, cache_dir: str | None = None) -> None:
        self._model = TextEmbedding(model_name, cache_dir=cache_dir)
        self.dimensions = dimensions

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        # ONNX inference is CPU-bound: keep it off the event loop.
        vectors = await asyncio.to_thread(lambda: list(self._model.passage_embed(list(texts))))
        return [self._checked(v.tolist()) for v in vectors]

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(lambda: list(self._model.query_embed([text])))
        return self._checked(vectors[0].tolist())

    def _checked(self, vector: list[float]) -> list[float]:
        if len(vector) != self.dimensions:
            raise ValueError(
                f"embedding model returned {len(vector)} dims, schema expects {self.dimensions}"
            )
        return vector


def to_pgvector(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
