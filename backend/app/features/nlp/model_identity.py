"""Which sentence-embedding model actually runs, and how it is named in
persisted identities (photo-card claim hash, embedding cache keys).

Until 2026-10-07 the embedding service ignored ML_EMBEDDING_MODEL_NAME and
always loaded LaBSE, while the setting said
`paraphrase-multilingual-mpnet-base-v2`. That setting value was nevertheless
folded into every photo-card claim hash. To keep those hashes (and cached
embeddings) valid:

* the legacy setting value is read as LaBSE, the model that actually ran;
* LaBSE keeps the legacy identity tag in hashes and the legacy cache key.

Any other model gets its own name in both places, so a genuine model change
still changes claim identity and never reuses vectors from another model.
"""

from __future__ import annotations

LABSE = "sentence-transformers/LaBSE"
LEGACY_EMBEDDING_SETTING = "paraphrase-multilingual-mpnet-base-v2"


def runtime_embedding_model(configured: str) -> str:
    """The model to load for a configured ML_EMBEDDING_MODEL_NAME."""
    name = (configured or "").strip()
    if not name or name == LEGACY_EMBEDDING_SETTING:
        return LABSE
    return name


def embedding_identity_tag(configured: str) -> str:
    """The embedding-model name used inside persisted claim identities."""
    model = runtime_embedding_model(configured)
    return LEGACY_EMBEDDING_SETTING if model == LABSE else model


def embedding_cache_prefix(configured: str, base: str) -> str:
    """Redis key prefix for cached vectors of the runtime model."""
    model = runtime_embedding_model(configured)
    return base if model == LABSE else f"{base}:{model}"
