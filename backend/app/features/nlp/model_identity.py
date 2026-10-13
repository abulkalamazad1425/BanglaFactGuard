
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
