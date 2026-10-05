"""Photo-card wiring: the same stages and headline rule as text claims, its own result identity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ClaimScope, PipelineStageID
from app.features.photocard.verification_stages import (
    PhotocardNormalizerStage,
    build_photocard_stages,
    compute_photocard_hash,
)
from app.features.verification.analysis.headline_comparison import HeadlineComparator
from app.features.verification.pipeline.factory import build_verification_stages
from app.features.verification.pipeline.stages.s09_headline_alteration import HeadlineAlterationStage
from app.shared.utils.hashing import compute_claim_hash
from pipeline_helpers import make_context

TITLE = "সরকার কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ দিয়েছে"


def _kwargs():
    return {name: MagicMock() for name in (
        "submission_repo", "result_repo", "article_repo", "source_repo", "cache_service",
        "embedding_service", "ner_service", "nli_service", "http_client",
    )}


def test_photo_cards_and_text_share_every_stage_but_the_normalizer():
    kwargs = _kwargs()
    text = build_verification_stages(**kwargs)
    card = build_photocard_stages(**kwargs)
    assert [s.stage_id for s in text] == [s.stage_id for s in card]
    assert type(card[0]) is PhotocardNormalizerStage
    assert all(type(a) is type(b) for a, b in zip(text[1:], card[1:]))
    headline = next(s for s in card if s.stage_id == PipelineStageID.S09_HEADLINE_ALTERATION)
    assert type(headline) is HeadlineAlterationStage
    comparator = headline._comparator
    assert isinstance(comparator, HeadlineComparator)
    assert comparator.nli is kwargs["nli_service"] and comparator.ner is kwargs["ner_service"]
    assert comparator.embedder is kwargs["embedding_service"]


async def test_photo_card_normalizer_rejects_a_body():
    ctx = make_context(TITLE, body="একটি সংযুক্ত বিবরণ যা ছবির কার্ডে থাকে না")
    with pytest.raises(ValueError):
        await PhotocardNormalizerStage(MagicMock()).execute(ctx)


async def test_photo_card_result_identity_is_isolated_from_text_claims():
    ctx = make_context(TITLE)
    repo = MagicMock(resolve_source=AsyncMock(return_value=None), get_by_canonical_name=AsyncMock(return_value=None))
    await PhotocardNormalizerStage(repo).execute(ctx)
    assert ctx.claim_scope == ClaimScope.HEADLINE_ONLY
    assert ctx.content_hash == compute_photocard_hash(TITLE, "prothomalo.com")
    assert ctx.content_hash != compute_claim_hash(TITLE, "prothomalo.com", ClaimScope.HEADLINE_ONLY)


def test_gemini_settings_do_not_affect_photo_card_identity(monkeypatch):
    from app.core.config import get_settings

    before = compute_photocard_hash(TITLE, "prothomalo.com")
    monkeypatch.setattr(get_settings().gemini, "model_name", "different-hosted-model")
    assert compute_photocard_hash(TITLE, "prothomalo.com") == before
