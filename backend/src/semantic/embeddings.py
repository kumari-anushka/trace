from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from typing import Protocol
from uuid import UUID

from src.semantic.models import EMBEDDING_DIMENSIONS, DistanceMetric
from src.semantic.repository import (
    EmbeddingInput,
    EmbeddingSpaceInput,
    SemanticRepository,
)

LOCAL_HASHING_ALGORITHM_VERSION = "local-hashing-v1"
DEFAULT_EMBEDDING_BATCH_SIZE = 64
MAX_EMBEDDING_BATCH_SIZE = 256
_TOKEN_PATTERN = re.compile(r"[\w./:@+-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class EmbeddingProviderInfo:
    provider: str
    model: str
    model_revision: str | None
    dimensions: int

    @property
    def canonical_key(self) -> str:
        revision = self.model_revision or "unversioned"
        return (
            f"{self.provider}:{self.model}:{revision}:"
            f"{self.dimensions}:{DistanceMetric.COSINE.value}"
        )


class EmbeddingProvider(Protocol):
    @property
    def info(self) -> EmbeddingProviderInfo: ...

    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingBuildSummary:
    provider: str
    model: str
    dimensions: int
    documents: int
    batches: int


class LocalHashingEmbeddingProvider:
    """Dependency-free local embeddings for reproducible development and tests.

    This uses feature hashing over normalized tokens and adjacent token pairs. It
    provides a lexical local baseline, not the semantic quality of a neural model.
    """

    @property
    def info(self) -> EmbeddingProviderInfo:
        return EmbeddingProviderInfo(
            provider="local",
            model="trace-feature-hashing",
            model_revision=LOCAL_HASHING_ALGORITHM_VERSION,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [_hash_text(text) for text in texts]


class EmbeddingBuilder:
    def __init__(
        self,
        *,
        semantic_repository: SemanticRepository,
        provider: EmbeddingProvider,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> None:
        if batch_size < 1 or batch_size > MAX_EMBEDDING_BATCH_SIZE:
            raise ValueError(
                f"embedding batch_size must be between 1 and {MAX_EMBEDDING_BATCH_SIZE}"
            )
        if provider.info.dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError(f"embedding provider must return {EMBEDDING_DIMENSIONS} dimensions")
        self.semantic_repository = semantic_repository
        self.provider = provider
        self.batch_size = batch_size

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> EmbeddingBuildSummary:
        provider_info = self.provider.info
        space = await self.semantic_repository.upsert_embedding_space(
            EmbeddingSpaceInput(
                canonical_key=provider_info.canonical_key,
                provider=provider_info.provider,
                model=provider_info.model,
                model_revision=provider_info.model_revision,
                dimensions=provider_info.dimensions,
                distance_metric=DistanceMetric.COSINE,
                is_active=True,
                provenance={
                    "component": "embedding_builder",
                    "provider": provider_info.provider,
                    "model": provider_info.model,
                    "model_revision": provider_info.model_revision,
                },
            )
        )

        document_count = 0
        batch_count = 0
        while True:
            documents = await self.semantic_repository.list_pending_documents(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                embedding_space_id=space.id,
                limit=self.batch_size,
            )
            if not documents:
                break

            vectors = await self.provider.embed([document.content for document in documents])
            if len(vectors) != len(documents):
                raise RuntimeError(
                    "embedding provider returned a different number of vectors than inputs"
                )

            for document, vector in zip(documents, vectors, strict=True):
                await self.semantic_repository.upsert_embedding(
                    EmbeddingInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        document_id=document.id,
                        embedding_space_id=space.id,
                        vector=vector,
                        content_hash=document.content_hash,
                        provenance={
                            "component": "embedding_builder",
                            "provider": provider_info.provider,
                            "model": provider_info.model,
                            "model_revision": provider_info.model_revision,
                        },
                        metadata={"canonical_space": provider_info.canonical_key},
                    )
                )
            document_count += len(documents)
            batch_count += 1

        return EmbeddingBuildSummary(
            provider=provider_info.provider,
            model=provider_info.model,
            dimensions=provider_info.dimensions,
            documents=document_count,
            batches=batch_count,
        )


def _hash_text(text: str) -> list[float]:
    tokens = _TOKEN_PATTERN.findall(text.casefold())
    features = list(tokens)
    features.extend(f"{left}\x1f{right}" for left, right in zip(tokens, tokens[1:], strict=False))
    if not features:
        features = [text.casefold() or "empty"]

    vector = [0.0] * EMBEDDING_DIMENSIONS
    for feature in features:
        digest = sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = -1.0 if digest[4] & 1 else 1.0
        vector[index] += sign

    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        fallback_digest = sha256(text.encode("utf-8")).digest()
        vector[int.from_bytes(fallback_digest[:4], "big") % EMBEDDING_DIMENSIONS] = 1.0
        magnitude = 1.0
    return [value / magnitude for value in vector]
