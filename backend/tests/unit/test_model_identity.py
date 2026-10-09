"""Embedding-model identity: the configured name, the model actually loaded,
and the name persisted inside photo-card claim hashes and cache keys."""

from datetime import date

import pytest

from app.core.config import get_settings
from app.features.nlp.model_identity import (
    LABSE,
    LEGACY_EMBEDDING_SETTING,
    embedding_cache_prefix,
    embedding_identity_tag,
    runtime_embedding_model,
)
from app.features.photocard.verification_stages import compute_photocard_hash

GOLDEN_CARD_HASH = "ad92cd767da07cf1cfe707c846f9e86dac0606e6673af009df85ab2ea512aae9"


@pytest.mark.parametrize("configured", [LABSE, LEGACY_EMBEDDING_SETTING, ""])
def test_labse_and_legacy_setting_share_the_historic_identity(configured):
    assert runtime_embedding_model(configured) == LABSE
    assert embedding_identity_tag(configured) == LEGACY_EMBEDDING_SETTING
    assert embedding_cache_prefix(configured, "bgf:emb") == "bgf:emb"


def test_a_different_model_changes_identity_and_cache_namespace():
    other = "intfloat/multilingual-e5-base"
    assert runtime_embedding_model(other) == other
    assert embedding_identity_tag(other) == other
    assert embedding_cache_prefix(other, "bgf:emb") == f"bgf:emb:{other}"


@pytest.mark.parametrize("configured", [LABSE, LEGACY_EMBEDDING_SETTING])
def test_photocard_hash_unchanged_by_the_setting_rename(monkeypatch, configured):
    monkeypatch.setattr(get_settings().ml, "embedding_model_name", configured)
    assert compute_photocard_hash(
        "ঢাকায় নতুন মেট্রোরেল চালু হয়েছে", "prothomalo.com", published_date=date(2026, 3, 15)
    ) == GOLDEN_CARD_HASH


def test_photocard_hash_changes_for_a_real_model_change(monkeypatch):
    monkeypatch.setattr(get_settings().ml, "embedding_model_name", "intfloat/multilingual-e5-base")
    assert compute_photocard_hash(
        "ঢাকায় নতুন মেট্রোরেল চালু হয়েছে", "prothomalo.com", published_date=date(2026, 3, 15)
    ) != GOLDEN_CARD_HASH
