"""
tests/unit/test_manipulation_details.py
=========================================
S10 (ManipulationDetectorStage) already computed *which* numbers were
altered (find_altered_numbers) and detected same-type entity substitution
(NERService.compute_typed_entity_substitution), but only ever surfaced a
bare boolean — the actual claimed-vs-article detail was logged and thrown
away, never reaching the API response or expert review. Business rule asked
for "alteration-detail extraction" (e.g. "১০ জন" vs "১০০ জন" claimed, or
which person/location/organisation was substituted for which).

Also covers the related durability gap found while wiring this up:
manipulation_flags was never persisted to the DB at all — it only ever lived
in the Redis result cache (PersistenceStage._update_redis_cache), so it
silently reverted to an all-False ManipulationFlagsSchema() once that cache
entry's TTL expired. The new verification_results_v2.manipulation_flags
JSONB column (migration b7d2e4f6a8c1) is the fix; this file covers the
repository plumbing for it.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ManipulationType
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.pipeline.stages.s10_manipulation_detector import (
    ManipulationDetectorStage,
)
from app.features.verification.repository import ResultV2Repository
from pipeline_helpers import article, make_context


async def _s10(context, ner_mentions=None, ner_available=True):
    context.claim_mentions = list(ner_mentions or [])
    context.evidence_mentions = list(ner_mentions or [])
    context.ner_available = ner_available
    return await ManipulationDetectorStage(None).execute(context)


@pytest.mark.asyncio
async def test_s10_surfaces_altered_number_details():
    ctx = make_context(
        "দুর্ঘটনায় ১০০ জন নিহত",
        top=article("দুর্ঘটনায় ১০ জন নিহত", "দুর্ঘটনায় ১০ জন নিহত হয়েছেন।"),
    )
    ctx = await _s10(ctx)
    flags = ctx.manipulation_flags
    assert flags.numbers_altered is True
    assert ManipulationType.NUMBERS_ALTERED in ctx.detected_manipulations
    detail = flags.altered_numbers[0]
    assert detail.claimed == "100" and detail.nearest_in_article == "10"  # digits normalised
    assert flags.check_states["numbers"].value == "FAILED"


@pytest.mark.asyncio
async def test_s10_surfaces_substituted_entity_only_for_same_type_and_role():
    claim = [EntityMention("শেখ হাসিনা", "PER"), EntityMention("ঢাকা", "LOC")]
    ev = [EntityMention("খালেদা জিয়া", "PER"), EntityMention("ঢাকা", "LOC")]
    ctx = make_context(
        "শেখ হাসিনা ঢাকায় সফর করলেন",
        top=article("খালেদা জিয়া ঢাকায় সফর করলেন", "খালেদা জিয়া ঢাকায় সফর করলেন।"),
    )
    ctx.claim_mentions, ctx.evidence_mentions, ctx.ner_available = claim, ev, True
    ctx = await ManipulationDetectorStage(None).execute(ctx)

    flags = ctx.manipulation_flags
    assert flags.entities_replaced is True
    detail = flags.substituted_entities[0]
    assert detail.entity_type == "PER"
    assert detail.claimed == ["শেখ হাসিনা"]
    assert detail.article_same_type == ["খালেদা জিয়া"]
    assert flags.discrepancies[0].kind == "entity_substitution"


@pytest.mark.asyncio
async def test_low_entity_overlap_alone_does_not_flag_substitution():
    # the claimed person is simply not mentioned; nothing of the same type
    # and role stands in their place -> no substitution is declared
    ctx = make_context(
        "শেখ হাসিনা ঢাকায় সফর করলেন",
        top=article("একজন নেতা ঢাকায় সফর করলেন", "একজন নেতা ঢাকায় সফর করলেন।"),
    )
    ctx = await _s10(ctx, [EntityMention("শেখ হাসিনা", "PER")])
    assert ctx.manipulation_flags.entities_replaced is False
    assert ctx.manipulation_flags.check_states["entities"].value == "PASSED"


@pytest.mark.asyncio
async def test_unrun_checks_are_not_reported_as_passed():
    ctx = make_context("শেখ হাসিনা ঢাকায় সফর করলেন", top=article("সম্পূর্ণ আলাদা শিরোনাম বিষয়", None))
    ctx = await _s10(ctx, [EntityMention("শেখ হাসিনা", "PER")], ner_available=False)
    states = {k: v.value for k, v in ctx.manipulation_flags.check_states.items()}
    assert states["entities"] == "NOT_EVALUATED"
    assert states["headline"] == "NOT_EVALUATED"  # no aligned source sentence -> not a pass
    assert states["body"] == "NOT_APPLICABLE"
    assert not ctx.manipulation_flags.any_manipulation_detected


# ─── ResultV2Repository.upsert_result — manipulation_flags plumbing ─────


@pytest.mark.asyncio
async def test_upsert_result_passes_manipulation_flags_to_create():
    repo = ResultV2Repository.__new__(ResultV2Repository)
    repo.session = AsyncMock()
    repo.get_by_submission_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    created_models: list = []

    async def fake_create(model):
        created_models.append(model)
        return model

    repo.create = fake_create  # type: ignore[method-assign]

    import uuid

    payload = {
        "headline_manipulated": False,
        "body_altered": False,
        "numbers_altered": True,
        "entities_replaced": False,
        "altered_numbers": [{"claimed": "১০০", "nearest_in_article": "১০"}],
        "substituted_entities": [],
    }

    await repo.upsert_result(
        uuid.uuid4(),
        source_status=None,
        content_status=None,
        date_status=None,
        confidence=0.5,
        reasoning="x",
        semantic_similarity=None,
        entity_match=None,
        contradiction_score=None,
        keyword_overlap=None,
        numerical_consistency=None,
        manipulation_flags=payload,
    )

    assert len(created_models) == 1
    assert created_models[0].manipulation_flags == payload


@pytest.mark.asyncio
async def test_upsert_result_passes_manipulation_flags_to_update():
    repo = ResultV2Repository.__new__(ResultV2Repository)
    repo.session = AsyncMock()
    existing = MagicMock()
    repo.get_by_submission_id = AsyncMock(return_value=existing)  # type: ignore[method-assign]

    update_calls: list = []

    async def fake_update(instance, **fields):
        update_calls.append((instance, fields))
        return instance

    repo.update = fake_update  # type: ignore[method-assign]

    import uuid

    payload = {"numbers_altered": True, "altered_numbers": [{"claimed": "৫০", "nearest_in_article": None}]}

    await repo.upsert_result(
        uuid.uuid4(),
        source_status=None,
        content_status=None,
        date_status=None,
        confidence=0.5,
        reasoning="x",
        semantic_similarity=None,
        entity_match=None,
        contradiction_score=None,
        keyword_overlap=None,
        numerical_consistency=None,
        manipulation_flags=payload,
    )

    assert len(update_calls) == 1
    _, fields = update_calls[0]
    assert fields["manipulation_flags"] == payload
