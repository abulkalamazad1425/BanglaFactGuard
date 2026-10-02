"""Scope-aware scoring and Source/Content/Date decisions (acceptance 1-11,
14, 15). Orchestration tests over deterministic fakes — they prove stage
logic, not model accuracy."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.constants import (
    CheckState,
    ClaimScope,
    ContentStatus,
    DateStatus,
    MetricState,
    SourceStatus,
)
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.text import chunk_text
from app.features.verification.pipeline.stages.s08_similarity_analyzer import (
    SimilarityAnalyzerStage,
)
from pipeline_helpers import FakeEmbedder, FakeNER, article, make_context, run_analysis

TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"
LEAD = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন। সেতুটি নির্মাণে তিন বছর সময় লেগেছে।"
UNRELATED = " ".join(f"আজ আবহাওয়া অধিদপ্তর জানিয়েছে তাপমাত্রা {i} ডিগ্রি থাকবে নদীর পানি বাড়ছে।" for i in range(40))
LONG_BODY = LEAD + " " + UNRELATED


async def _s08(ctx, ner=None, embedder=None):
    embedder = embedder or FakeEmbedder()
    await SimilarityAnalyzerStage(embedder, ner or FakeNER()).execute(ctx)
    return ctx, embedder


# ── 1-3: headline-only scoring ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_headline_only_never_computes_submitted_body_similarity():
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LONG_BODY))
    ctx.normalized_body = "এই টেক্সট কখনো তুলনায় আসা উচিত নয়"  # defence in depth
    ctx, embedder = await _s08(ctx)

    assert ctx.scores.body_similarity is None
    assert ctx.analysis.metrics["body_similarity"].state == MetricState.NOT_APPLICABLE
    assert ctx.analysis.metrics["body_keyword_coverage"].state == MetricState.NOT_APPLICABLE
    # the only direct comparison is headline <-> source title
    assert embedder.similarity_calls == [(TITLE, TITLE)]
    # the whole article body is never embedded as if it were a body match,
    # and nothing of the (forbidden) submitted body is
    encoded = [t for batch in embedder.batch_calls for t in batch]
    assert all(LONG_BODY != t and "তুলনায় আসা উচিত নয়" not in t for t in encoded)
    assert all(len(t) <= 700 for t in encoded)


@pytest.mark.asyncio
async def test_photocard_style_result_has_null_body_similarity():
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LONG_BODY))
    await _s08(ctx)
    assert ctx.scores.model_dump()["body_similarity"] is None
    assert ctx.scores.model_dump()["body_keyword_coverage"] is None


@pytest.mark.asyncio
async def test_unrelated_paragraphs_do_not_depress_an_exact_headline_match():
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LONG_BODY))
    await _s08(ctx)
    assert ctx.scores.headline_similarity == pytest.approx(1.0, abs=1e-3)
    assert ctx.scores.semantic_similarity == pytest.approx(ctx.scores.headline_similarity)
    assert ctx.scores.headline_keyword_coverage == 1.0
    # supporting passage evidence is separate and selected with context
    assert ctx.scores.passage_similarity is not None and ctx.scores.passage_similarity > 0.8
    assert ctx.analysis.passages and "উদ্বোধন" in ctx.analysis.passages[0].text


# ── 4: submitted body only for text-with-body ────────────────────────────


@pytest.mark.asyncio
async def test_submitted_body_is_compared_chunkwise_for_text_with_body():
    submitted = LEAD + " " + UNRELATED
    ctx = make_context(TITLE, body=submitted, top=article(TITLE, LONG_BODY))
    assert ctx.claim_scope == ClaimScope.HEADLINE_WITH_BODY
    ctx, embedder = await _s08(ctx)

    assert ctx.analysis.metrics["body_similarity"].state == MetricState.COMPUTED
    assert ctx.scores.body_similarity is not None
    assert ctx.scores.semantic_similarity == pytest.approx(
        0.3 * ctx.scores.headline_similarity + 0.7 * ctx.scores.body_similarity
    )
    # the headline is NOT prepended to the body for the body metric
    claim_chunks, _ = chunk_text(submitted, max_chars=450, max_chunks=120)
    assert any(batch[: len(claim_chunks)] == claim_chunks for batch in embedder.batch_calls)
    details = ctx.analysis.metrics["body_similarity"].details
    assert details["claim_chunks"] == len(claim_chunks)


@pytest.mark.asyncio
async def test_long_submitted_body_is_not_truncated_and_keeps_its_tail():
    tail = "সর্বশেষ অনুচ্ছেদে ৯৯৯ কোটি টাকার কথা বলা হয়েছে।"
    submitted = LEAD + " " + UNRELATED * 3 + " " + tail
    ctx = make_context(TITLE, body=submitted, top=article(TITLE, LONG_BODY))
    ctx, embedder = await _s08(ctx)
    encoded = [t for batch in embedder.batch_calls for t in batch]
    assert any("৯৯৯" in t for t in encoded), "the tail of a long body must be compared"
    assert ctx.body_complete is True


# ── 5-6: entity coverage ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_claim_entities_present_with_extra_article_entities_is_complete():
    known = [EntityMention("ঢাকা", "LOC"), EntityMention("চট্টগ্রাম", "LOC"), EntityMention("সিলেট", "LOC")]
    body = LEAD + " অনুষ্ঠানে চট্টগ্রাম ও সিলেট থেকেও অতিথিরা এসেছিলেন।"
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, body))
    await _s08(ctx, ner=FakeNER(known))
    assert ctx.scores.entity_match == 1.0
    assert ctx.analysis.metrics["entity_match"].state == MetricState.COMPUTED


@pytest.mark.asyncio
async def test_missing_entity_exposes_diagnostics():
    known = [EntityMention("ঢাকা", "LOC"), EntityMention("রংপুর", "LOC")]
    ctx = make_context(
        "প্রধান উপদেষ্টা রংপুরে নতুন সেতুর উদ্বোধন করেছেন ঢাকা",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(TITLE, LEAD),
    )
    await _s08(ctx, ner=FakeNER(known))
    d = ctx.analysis.metrics["entity_match"].details
    assert d["unmatched"] == ["রংপুর"]
    assert d["matched"] == ["ঢাকা"]
    assert ctx.scores.entity_match == 0.5


@pytest.mark.asyncio
async def test_no_claim_entities_is_not_applicable_and_ner_down_is_unavailable():
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LEAD))
    await _s08(ctx, ner=FakeNER([]))
    assert ctx.scores.entity_match is None
    assert ctx.analysis.metrics["entity_match"].state == MetricState.NOT_APPLICABLE

    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LEAD))
    await _s08(ctx, ner=FakeNER([EntityMention("ঢাকা", "LOC")], available=False))
    assert ctx.scores.entity_match is None
    assert ctx.analysis.metrics["entity_match"].state == MetricState.UNAVAILABLE


# ── 7-8: keyword coverage ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_identical_titles_give_complete_keyword_coverage_even_with_long_body():
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LONG_BODY))
    await _s08(ctx)
    assert ctx.scores.keyword_overlap == 1.0 == ctx.scores.headline_keyword_coverage
    assert ctx.analysis.metrics["headline_keyword_coverage"].details["unmatched"] == []


@pytest.mark.asyncio
async def test_inflection_and_phrase_differences_do_not_create_zero_coverage():
    ctx = make_context(
        "প্রধানমন্ত্রী ঢাকায় সেতুর উদ্বোধন",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("প্রধান মন্ত্রী ঢাকা শহরে সেতু উদ্বোধন করেছেন", LEAD),
    )
    await _s08(ctx)
    assert ctx.scores.keyword_overlap == 1.0


# ── 9: evidence-backed alteration ───────────────────────────────────────

SRC_TITLE = "সরকার শুল্ক কমিয়েছে ১০ শতাংশ"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim, kind",
    [
        ("সরকার শুল্ক কমায়নি ১০ শতাংশ", "negation"),
        ("সরকার শুল্ক কমিয়েছে ২০ শতাংশ", "numbers"),
    ],
)
async def test_changed_negation_or_number_is_evidence_backed_alteration(claim, kind):
    ctx = make_context(claim, scope=ClaimScope.HEADLINE_ONLY, top=article(SRC_TITLE, SRC_TITLE + "।"))
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.content_status == ContentStatus.ALTERED
    assert [d.kind for d in ctx.manipulation_flags.discrepancies] == [kind]
    d = ctx.manipulation_flags.discrepancies[0]
    assert d.claim_text and d.evidence_text  # quotable on both sides


@pytest.mark.asyncio
async def test_changed_scope_is_alteration():
    ctx = make_context(
        "সকল শিক্ষার্থী বৃত্তি পেয়েছে",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("কিছু শিক্ষার্থী বৃত্তি পেয়েছে", "কিছু শিক্ষার্থী বৃত্তি পেয়েছে।"),
    )
    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.ALTERED
    assert ctx.manipulation_flags.check_states["scope"] == CheckState.FAILED


@pytest.mark.asyncio
async def test_swapped_entity_roles_are_alteration():
    ms = [EntityMention("আব্দুল করিম", "PER"), EntityMention("রফিক", "PER")]
    ctx = make_context(
        "আব্দুল করিম রফিককে মেরেছেন",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("রফিক আব্দুল করিমকে মেরেছেন", "রফিক আব্দুল করিমকে মেরেছেন।"),
    )
    ctx = await run_analysis(ctx, ner=FakeNER(ms))
    assert ctx.content_status == ContentStatus.ALTERED
    assert ctx.manipulation_flags.entities_replaced is True
    assert ctx.manipulation_flags.check_states["entities"] == CheckState.FAILED


@pytest.mark.asyncio
async def test_high_similarity_cannot_cancel_a_material_discrepancy():
    # one changed number in an otherwise identical headline: similarity ~high
    ctx = make_context(
        "সরকার ১০০ কোটি টাকা বরাদ্দ দিয়েছে বন্যা দুর্গতদের জন্য",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(
            "সরকার ১০ কোটি টাকা বরাদ্দ দিয়েছে বন্যা দুর্গতদের জন্য",
            "সরকার ১০ কোটি টাকা বরাদ্দ দিয়েছে বন্যা দুর্গতদের জন্য।",
        ),
    )
    ctx = await run_analysis(ctx)
    assert ctx.scores.headline_similarity > 0.8
    assert ctx.content_status == ContentStatus.ALTERED


# ── 10: matching headline, altered body ─────────────────────────────────

SRC_BODY = "সরকার নতুন সেতু উদ্বোধন করেছে। সেতু নির্মাণে ৫০০ কোটি টাকা ব্যয় হয়েছে। সেতুটি দুই বছরে তৈরি হয়েছে।"


@pytest.mark.asyncio
async def test_matching_headline_with_altered_body_is_not_matched():
    claim_body = "সরকার নতুন সেতু উদ্বোধন করেছে। সেতু নির্মাণে ৯০০ কোটি টাকা ব্যয় হয়েছে। সেতুটি দুই বছরে তৈরি হয়েছে।"
    ctx = make_context(
        "সরকার নতুন সেতু উদ্বোধন করেছে",
        body=claim_body,
        top=article("সরকার নতুন সেতু উদ্বোধন করেছে", SRC_BODY),
    )
    ctx = await run_analysis(ctx)
    assert ctx.manipulation_flags.check_states["headline"] == CheckState.PASSED
    assert ctx.manipulation_flags.check_states["body"] == CheckState.FAILED
    assert ctx.manipulation_flags.body_altered is True
    assert ctx.content_status == ContentStatus.ALTERED
    assert {d.part for d in ctx.manipulation_flags.discrepancies} == {"body"}


@pytest.mark.asyncio
async def test_matching_text_with_body_is_matched():
    ctx = make_context(
        "সরকার নতুন সেতু উদ্বোধন করেছে",
        body=SRC_BODY,
        top=article("সরকার নতুন সেতু উদ্বোধন করেছে", SRC_BODY),
    )
    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.MATCHED, ctx.analysis.content_basis
    assert ctx.manipulation_flags.check_states["body"] == CheckState.PASSED


@pytest.mark.asyncio
async def test_photocard_scope_marks_body_check_not_applicable_and_never_flags_body():
    ctx = make_context(
        "সরকার নতুন সেতু উদ্বোধন করেছে",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("সরকার নতুন সেতু উদ্বোধন করেছে", SRC_BODY),
    )
    ctx = await run_analysis(ctx)
    assert ctx.manipulation_flags.check_states["body"] == CheckState.NOT_APPLICABLE
    assert ctx.manipulation_flags.body_altered is False
    assert ctx.content_status == ContentStatus.MATCHED


# ── 11: weak/ambiguous scores are Incomplete, not Altered ───────────────


@pytest.mark.asyncio
async def test_weak_scores_without_concrete_discrepancy_are_incomplete():
    ctx = make_context(
        "নতুন সেতুর উদ্বোধন হলো ঢাকায় আজ",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(TITLE, LEAD),
    )
    ctx = await run_analysis(ctx)
    assert ctx.manipulation_flags.discrepancies == []
    assert ctx.content_status in {ContentStatus.INCOMPLETE, ContentStatus.MATCHED}
    assert ctx.content_status != ContentStatus.ALTERED


@pytest.mark.asyncio
async def test_missing_signals_and_neutral_nli_alone_are_incomplete_never_altered():
    ctx = make_context(
        "ঢাকায় সেতুর উদ্বোধন",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(TITLE, None),  # no article body: weak evidence
    )
    ctx = await run_analysis(ctx, ner=FakeNER([], available=False))
    assert ctx.content_status != ContentStatus.ALTERED
    assert ctx.content_status == ContentStatus.INCOMPLETE  # NER unavailable + no body


@pytest.mark.asyncio
async def test_high_nli_contradiction_without_validation_cannot_alone_alter_content():
    from unittest.mock import AsyncMock, MagicMock

    from app.features.verification.schemas import NLIScoresSchema

    nli = MagicMock()
    nli.predict = AsyncMock(return_value=NLIScoresSchema(entailment=0.0, contradiction=0.95, neutral=0.05))
    ctx = make_context(TITLE, scope=ClaimScope.HEADLINE_ONLY, top=article(TITLE, LEAD))
    ctx = await run_analysis(ctx, nli=nli)
    assert ctx.content_status == ContentStatus.INCOMPLETE
    assert any("contradiction" in b for b in ctx.analysis.content_basis)


@pytest.mark.asyncio
async def test_low_contradiction_is_not_treated_as_entailment():
    # unrelated-support case: contradiction low, but support thresholds unmet
    ctx = make_context(
        "ক্রিকেট দল ঢাকায় অনুশীলন করেছে",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(TITLE, LEAD),
    )
    ctx = await run_analysis(ctx)
    assert ctx.content_status != ContentStatus.MATCHED


# ── 14-15: date is independent of content ───────────────────────────────


@pytest.mark.asyncio
async def test_correct_content_with_wrong_claimed_date_is_matched_and_mismatched():
    ctx = make_context(
        TITLE,
        scope=ClaimScope.HEADLINE_ONLY,
        published_date=date(2026, 6, 8),
        top=article(TITLE, LEAD, published=date(2026, 6, 7)),
    )
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.MISMATCHED
    assert ctx.analysis.date.provenance == "json_ld.datePublished"


@pytest.mark.asyncio
async def test_matching_claimed_date_is_matched():
    ctx = make_context(TITLE, published_date=date(2026, 6, 7), top=article(TITLE, LEAD, published=date(2026, 6, 7)))
    ctx = await run_analysis(ctx)
    assert ctx.date_status == DateStatus.MATCHED


@pytest.mark.asyncio
async def test_missing_publication_date_is_incomplete_not_mismatched():
    ctx = make_context(TITLE, published_date=date(2026, 6, 7), top=article(TITLE, LEAD, published=None))
    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.INCOMPLETE


@pytest.mark.asyncio
async def test_no_claimed_date_makes_date_not_applicable():
    ctx = make_context(TITLE, published_date=None, top=article(TITLE, LEAD))
    ctx = await run_analysis(ctx)
    assert ctx.date_status is None


# ── source decisions from correspondence, not content ───────────────────


@pytest.mark.asyncio
async def test_same_outlet_similar_topic_is_not_enough_for_source_confirmed():
    ctx = make_context(
        "ক্রিকেট বিশ্বকাপ বাংলাদেশ দলের জয়",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("বাজেটে শিক্ষা খাতে বরাদ্দ বেড়েছে", "বাজেটে শিক্ষা খাতে বরাদ্দ বেড়েছে।"),
    )
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.NOT_FOUND
    assert ctx.content_status is None and ctx.date_status is None


@pytest.mark.asyncio
async def test_inadequate_search_with_non_corresponding_article_is_incomplete():
    ctx = make_context(
        "ক্রিকেট বিশ্বকাপ বাংলাদেশ দলের জয়",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article("বাজেটে শিক্ষা খাতে বরাদ্দ বেড়েছে", "বাজেটে শিক্ষা খাতে বরাদ্দ বেড়েছে।"),
        search_adequate=False,
    )
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE


@pytest.mark.asyncio
async def test_defective_aggregate_cannot_override_strong_correspondence():
    # strong headline/title correspondence with an altered detail stays CONFIRMED
    ctx = make_context(
        "সরকার শুল্ক কমিয়েছে ২০ শতাংশ",
        scope=ClaimScope.HEADLINE_ONLY,
        top=article(SRC_TITLE, SRC_TITLE + "।"),
    )
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.content_status == ContentStatus.ALTERED
