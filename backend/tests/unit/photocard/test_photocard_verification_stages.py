"""A photo card runs the same S01-S13 stages as a text claim; only its
normaliser (headline only, its own result identity) differs."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.core.constants import ClaimScope
from app.features.nlp.model_identity import LABSE, LEGACY_EMBEDDING_SETTING
from app.features.photocard.verification_stages import (
    PhotocardNormalizerStage,
    build_photocard_stages,
    compute_photocard_hash,
)
from app.features.verification import source_policy
from app.features.verification.pipeline.factory import build_verification_stages
from app.shared.utils.hashing import compute_claim_hash
from tests.helpers.pipeline import FakeSourceRepo, make_context, source_record

TITLE = "সরকার কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ দিয়েছে"
GOLDEN = ("ঢাকায় নতুন মেট্রোরেল চালু হয়েছে", "prothomalo.com", date(2026, 3, 15))


def test_photo_cards_and_text_claims_share_every_stage_but_the_normaliser():
    kwargs = {name: MagicMock() for name in ("submission_repo", "result_repo", "article_repo", "source_repo", "cache_service",
                                             "embedding_service", "ner_service", "nli_service", "http_client")}
    text, card = build_verification_stages(**kwargs), build_photocard_stages(**kwargs)
    assert [s.stage_id for s in text] == [s.stage_id for s in card]
    assert type(card[0]) is PhotocardNormalizerStage
    assert all(type(a) is type(b) for a, b in zip(text[1:], card[1:], strict=True))


async def test_the_card_identity_is_headline_only_and_never_a_text_claims():
    repo = FakeSourceRepo(source_record("prothomalo.com"))
    with pytest.raises(ValueError):
        await PhotocardNormalizerStage(repo).execute(make_context(TITLE, body="ছবির কার্ডে বিবরণ থাকে না"))
    ctx = await PhotocardNormalizerStage(repo).execute(make_context(TITLE))
    assert ctx.claim_scope == ClaimScope.HEADLINE_ONLY
    assert ctx.content_hash == compute_photocard_hash(TITLE, "prothomalo.com")
    assert ctx.content_hash != compute_claim_hash(TITLE, "prothomalo.com", ClaimScope.HEADLINE_ONLY)

    no_source = make_context(TITLE)
    no_source.raw_claimed_source = ""
    ctx = await PhotocardNormalizerStage(repo).execute(no_source)
    assert ctx.verification_mode == source_policy.VERIFIED_SOURCES
    assert ctx.content_hash == compute_photocard_hash(TITLE, source_policy.verified_identity_key(ctx.verified_scope))


@pytest.mark.parametrize("configured", [LABSE, LEGACY_EMBEDDING_SETTING])
def test_the_persisted_card_identity_is_stable(monkeypatch, configured):
    """Golden value: these hashes are stored and reused. The embedding setting's
    rename (to the model that always ran) and the Gemini settings never change it."""
    monkeypatch.setattr(get_settings().ml, "embedding_model_name", configured)
    monkeypatch.setattr(get_settings().gemini, "model_name", "different-hosted-model")
    headline, source, published = GOLDEN
    assert compute_photocard_hash(headline, source, published_date=published) == (
        "ad92cd767da07cf1cfe707c846f9e86dac0606e6673af009df85ab2ea512aae9"
    )
    assert compute_photocard_hash(headline, source) == "ed052df03ae8bffaaad082c0045b9b4b8646fc8004303df00e7500997944655e"


def test_a_real_model_change_changes_the_identity(monkeypatch):
    monkeypatch.setattr(get_settings().ml, "embedding_model_name", "intfloat/multilingual-e5-base")
    headline, source, published = GOLDEN
    assert compute_photocard_hash(headline, source, published_date=published) != (
        "ad92cd767da07cf1cfe707c846f9e86dac0606e6673af009df85ab2ea512aae9"
    )
