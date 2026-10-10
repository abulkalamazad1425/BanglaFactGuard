"""The legacy embedding setting name is read as LaBSE (the model that always
ran) and keeps its historic identity; any other model gets a new one."""

import pytest

from app.features.nlp.model_identity import (
    LABSE,
    LEGACY_EMBEDDING_SETTING,
    embedding_cache_prefix,
    embedding_identity_tag,
    runtime_embedding_model,
)


@pytest.mark.parametrize("configured", [LABSE, LEGACY_EMBEDDING_SETTING, "", "  "])
def test_labse_and_the_legacy_setting_share_the_historic_identity(configured):
    assert runtime_embedding_model(configured) == LABSE
    assert embedding_identity_tag(configured) == LEGACY_EMBEDDING_SETTING
    assert embedding_cache_prefix(configured, "bgf:emb") == "bgf:emb"


def test_a_different_model_changes_identity_and_cache_namespace():
    other = "intfloat/multilingual-e5-base"
    assert runtime_embedding_model(other) == embedding_identity_tag(other) == other
    assert embedding_cache_prefix(other, "bgf:emb") == f"bgf:emb:{other}"
