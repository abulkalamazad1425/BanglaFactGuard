"""Statement-by-statement content comparison (analysis/content_check.py).

NLI/embeddings/NER are deterministic stand-ins: these pin the decision policy
(MATCHED / ALTERED / INCOMPLETE and why), not the local models' accuracy.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.constants import CheckState, ClaimScope, ContentStatus, DateStatus, SourceStatus
from app.features.verification.analysis.content_check import (
    ContentComparator,
    content_flags,
    quantities,
    split_statements,
)
from app.features.verification.analysis.decisions import decide_content
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.schemas import AnalysisDetails, NLIScoresSchema
from pipeline_helpers import FakeEmbedder, FakeNER, article, make_context

TITLE = "সরকার কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ দিয়েছে"
BODY = (
    "ঢাকা, ৩ অক্টোবর। কৃষকদের সহায়তায় সরকার ১০ কোটি টাকা বরাদ্দ দিয়েছে। "
    "কৃষি মন্ত্রণালয় জানিয়েছে, এই টাকা আগামী মাসে বিতরণ করা হবে। "
    "বন্যায় ক্ষতিগ্রস্ত ৫০ হাজার কৃষক এই সহায়তা পাবেন। "
    "মন্ত্রী বলেন, পানি নেমে গেলে বীজ দেওয়া হবে।"
)


def nli(e=0.3, c=0.1):
    return MagicMock(predict=AsyncMock(return_value=NLIScoresSchema(entailment=e, contradiction=c, neutral=1 - e - c)))


async def compare(headline, title=TITLE, body=BODY, *, claim_body=None, model=None, ner=None, embedder=None, validated=False):
    comparator = ContentComparator(embedder or FakeEmbedder(), model or nli(), ner or FakeNER(), nli_validated=validated)
    return await comparator.compare(headline, claim_body, title, body)


async def status_of(headline, title=TITLE, body=BODY, **kw):
    result = await compare(headline, title, body, **kw)
    return decide_content(result)[0], result


# ── exact copies are MATCHED ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "title, body",
    [
        (TITLE, BODY),
        (TITLE + " | প্রথম আলো", BODY),             # site suffix on the title
        (TITLE, ""),                                 # source body not extracted
        ("কৃষি খাতে নতুন সহায়তা", BODY),            # headline is the lead sentence, not the title
    ],
    ids=["title", "title-suffix", "title-only-source", "lead-sentence"],
)
async def test_exact_headline_is_matched(title, body):
    headline = TITLE if title != "কৃষি খাতে নতুন সহায়তা" else "কৃষকদের সহায়তায় সরকার ১০ কোটি টাকা বরাদ্দ দিয়েছে"
    status, result = await status_of(headline, title, body)
    assert status == ContentStatus.MATCHED, result
    assert result.findings[0].basis == "verbatim"


async def test_exact_copy_is_matched_whatever_an_unvalidated_nli_or_competing_sentence_says():
    model = nli(0.0, 0.97)
    status, _ = await status_of(TITLE, body=TITLE.replace("১০", "৫০") + "। সংশোধন: আগের তথ্যটি সঠিক নয়।", model=model)
    assert status == ContentStatus.MATCHED
    model.predict.assert_not_awaited()  # verbatim support needs no model


async def test_full_article_copy_with_body_is_matched():
    status, result = await status_of(TITLE, claim_body=BODY)
    assert status == ContentStatus.MATCHED, result
    assert {f.part for f in result.findings} == {"headline", "body"}
    # the dateline is not a material statement
    assert all(f.claim_text != "ঢাকা, ৩ অক্টোবর।" for f in result.findings)


async def test_long_body_copy_is_compared_to_its_tail_without_nli():
    filler = " ".join(f"আজ জেলার {i} নম্বর ওয়ার্ডে কৃষকদের সভা হয়েছে।" for i in range(60))
    body = filler + " " + BODY
    model = nli()
    status, result = await status_of(TITLE, body=body, claim_body=body, model=model)
    assert status == ContentStatus.MATCHED
    model.predict.assert_not_awaited()


# ── summaries and paraphrases are MATCHED ────────────────────────────────


async def test_condensed_headline_is_matched():
    status, result = await status_of("কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ")
    assert status == ContentStatus.MATCHED


async def test_reordered_headline_with_all_facts_is_matched_without_nli():
    status, result = await status_of("১০ কোটি টাকা বরাদ্দ দিয়েছে সরকার কৃষকদের জন্য")
    assert status == ContentStatus.MATCHED
    assert result.findings[0].basis == "facts_preserved"


async def test_paraphrase_is_matched_on_local_entailment():
    status, result = await status_of("কৃষকদের সহায়তায় ১০ কোটি টাকা দিল সরকার", model=nli(0.92, 0.02))
    assert status == ContentStatus.MATCHED
    assert result.findings[0].basis == "entailment"


async def test_headline_joining_title_and_a_lead_detail_is_matched():
    status, result = await status_of("কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ, পাবেন ৫০ হাজার কৃষক")
    assert status == ContentStatus.MATCHED
    assert result.findings[0].basis == "clauses"


async def test_summarised_body_is_matched():
    claim_body = (
        "সরকার কৃষকদের সহায়তায় ১০ কোটি টাকা বরাদ্দ দিয়েছে। "
        "বন্যায় ক্ষতিগ্রস্ত ৫০ হাজার কৃষক সহায়তা পাবেন।"
    )
    status, result = await status_of(TITLE, claim_body=claim_body)
    assert status == ContentStatus.MATCHED, result


async def test_dropping_a_neutral_reporting_attribution_is_still_matched():
    source = "পুলিশ জানিয়েছে, দুর্ঘটনায় ৫ জন নিহত হয়েছেন।"
    status, _ = await status_of("দুর্ঘটনায় ৫ জন নিহত হয়েছেন", "সড়কে প্রাণ গেল পাঁচজনের", source)
    assert status == ContentStatus.MATCHED


@pytest.mark.parametrize(
    "claim, source",
    [
        ("বন্যার পানি নেমে গেছে শহরে", "শহরে বন্যার পানি নেমে গেছে"),          # পানি is not a negation
        ("নির্বাচন সুষ্ঠুভাবে সম্পন্ন হয়েছে", "সুষ্ঠুভাবে নির্বাচন সম্পন্ন হয়েছে"),  # -ভাবে is not future
        ("ড. ইউনূস নতুন সেতুর উদ্বোধন করেছেন", "ড. ইউনূস নতুন সেতুর উদ্বোধন করেছেন"),  # ড. is not a sentence end
    ],
)
async def test_bangla_surface_forms_do_not_create_false_differences(claim, source):
    status, result = await status_of(claim, source, source + "।")
    assert status == ContentStatus.MATCHED, result


# ── concrete changes are ALTERED, with both texts quoted ─────────────────


@pytest.mark.parametrize(
    "claim, source, kind",
    [
        (TITLE.replace("১০", "২০"), TITLE, "numbers"),
        ("দুর্ঘটনায় ২০ জন নিহত ও ৫ জন আহত", "দুর্ঘটনায় ৫ জন নিহত ও ২০ জন আহত", "numbers"),
        ("সরকার শুল্ক কমায়নি", "সরকার শুল্ক কমিয়েছে", "negation"),
        ("সরকার নতুন কর আরোপ করেছে", "সরকার নতুন কর আরোপের পরিকল্পনা করছে", "modality"),
        ("সকল শিক্ষার্থী বৃত্তি পেয়েছে", "কিছু শিক্ষার্থী বৃত্তি পেয়েছে", "scope"),
        ("প্রকল্পে দুর্নীতি হয়নি", "মন্ত্রী দাবি করেছেন প্রকল্পে দুর্নীতি হয়নি", "attribution"),
    ],
)
async def test_concrete_changes_are_altered(claim, source, kind):
    status, result = await status_of(claim, source, source + "।")
    assert status == ContentStatus.ALTERED, result
    finding = result.findings[0]
    assert finding.kind == kind and finding.evidence and finding.evidence[0].quote


async def test_entity_role_swap_is_altered():
    people = [EntityMention("আব্দুল করিম", "PER"), EntityMention("রফিক", "PER")]
    source = "রফিক আব্দুল করিমকে মেরেছেন"
    status, result = await status_of("আব্দুল করিম রফিককে মেরেছেন", source, source + "।", ner=FakeNER(people))
    assert status == ContentStatus.ALTERED
    assert result.findings[0].kind == "entity_role"


async def test_changed_detail_from_the_body_is_altered_in_a_headline():
    status, result = await status_of("কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ, পাবেন ৮০ হাজার কৃষক")
    assert status == ContentStatus.ALTERED
    assert "৮০" in result.findings[0].explanation and "৫০" in result.findings[0].explanation


async def test_correct_headline_with_altered_body_is_altered():
    claim_body = "সরকার কৃষকদের সহায়তায় ১০ কোটি টাকা বরাদ্দ দিয়েছে। বন্যায় ক্ষতিগ্রস্ত ৯০ হাজার কৃষক এই সহায়তা পাবেন।"
    result = await compare(TITLE, claim_body=claim_body)
    status, basis = decide_content(result)
    assert status == ContentStatus.ALTERED
    flags, _ = content_flags(result, with_body=True)
    assert flags.check_states["headline"] == CheckState.PASSED
    assert flags.check_states["body"] == CheckState.FAILED
    assert flags.body_altered and not flags.headline_manipulated
    assert flags.altered_numbers[0].claimed.startswith("৯০")


async def test_rule_wins_over_an_nli_reading_that_ignores_a_changed_number():
    status, _ = await status_of(TITLE.replace("১০", "৫০"), model=nli(0.95, 0.01))
    assert status == ContentStatus.ALTERED


# ── missing or ambiguous evidence is INCOMPLETE, never ALTERED ───────────


async def test_statement_absent_from_the_source_is_incomplete():
    claim_body = "সরকার কৃষকদের সহায়তায় ১০ কোটি টাকা বরাদ্দ দিয়েছে। প্রধানমন্ত্রী নিজে জেলায় জেলায় টাকা বিতরণ করবেন।"
    status, result = await status_of(TITLE, claim_body=claim_body)
    assert status == ContentStatus.INCOMPLETE
    assert [f.status for f in result.findings].count("INSUFFICIENT_EVIDENCE") == 1


async def test_different_action_is_not_mistaken_for_negation():
    # "did not raise" is not the negation of "reduced": unsupported, not altered
    status, result = await status_of("সরকার শুল্ক বাড়ায়নি", "সরকার শুল্ক কমিয়েছে", "সরকার শুল্ক কমিয়েছে।")
    assert status == ContentStatus.INCOMPLETE


async def test_unvalidated_nli_contradiction_alone_is_not_altered():
    status, _ = await status_of("কৃষকদের সাহায্য দিতে সরকার অর্থ বরাদ্দ করেছে", model=nli(0.02, 0.95))
    assert status == ContentStatus.INCOMPLETE


async def test_validated_nli_contradiction_on_an_aligned_passage_is_altered():
    status, result = await status_of(
        "কৃষকদের সহায়তায় সরকার টাকা বরাদ্দ বাতিল করেছে", model=nli(0.01, 0.96), validated=True
    )
    assert status == ContentStatus.ALTERED
    assert result.findings[0].kind == "semantic"


async def test_paraphrase_without_semantic_confirmation_is_incomplete():
    failed = MagicMock(encode_batch=AsyncMock(side_effect=RuntimeError("offline")))
    missing = MagicMock(predict=AsyncMock(return_value=None))
    status, _ = await status_of("কৃষকদের সহায়তায় অর্থ দিচ্ছে সরকার", embedder=failed, model=missing)
    assert status == ContentStatus.INCOMPLETE
    # ...while an exact copy needs neither model
    status, _ = await status_of(TITLE, embedder=failed, model=missing)
    assert status == ContentStatus.MATCHED


async def test_named_person_missing_from_the_source_blocks_entailment():
    source = "মিরপুরে একজন গ্রেপ্তার হয়েছেন"
    status, _ = await status_of(
        "রহিম মিরপুরে গ্রেপ্তার হয়েছেন", source, source + "।",
        ner=FakeNER([EntityMention("রহিম", "PER")]), model=nli(0.95, 0.01),
    )
    assert status == ContentStatus.INCOMPLETE


async def test_number_found_elsewhere_in_the_article_is_not_support():
    source = "কৃষকদের জন্য টাকা বরাদ্দ দিয়েছে সরকার। অন্য ঘটনায় ৫০ জন নিহত।"
    status, _ = await status_of(TITLE.replace("১০", "৫০"), "কৃষি সংবাদ", source, model=nli(0.95, 0.01))
    assert status != ContentStatus.MATCHED


async def test_source_that_denies_the_statement_does_not_support_it():
    source = "সরকার কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ দিয়েছে বলে ছড়ানো খবরটি গুজব।"
    status, _ = await status_of("কৃষকদের জন্য ১০ কোটি টাকা বরাদ্দ দিল সরকার", "কৃষি সংবাদ", source)
    assert status == ContentStatus.INCOMPLETE


async def test_headline_without_comparable_content_cannot_be_decided():
    result = await compare("!!!")
    assert result.reason and decide_content(result)[0] == ContentStatus.INCOMPLETE


# ── the same check for photo cards and both text scopes ──────────────────


async def classify(headline, *, body=None, scope=None, published=None):
    ctx = make_context(headline, body=body, scope=scope, top=article(TITLE, BODY), published_date=published)
    ctx.analysis.metrics.clear()
    from app.core.constants import MetricState
    from app.features.verification.schemas import MetricDetail

    ctx.analysis.metrics["headline_similarity"] = MetricDetail(state=MetricState.COMPUTED, value=0.95)
    comparator = ContentComparator(FakeEmbedder(), nli(), FakeNER(), nli_validated=False)
    return await ClassifierStage(comparator).execute(ctx)


async def test_date_mismatch_never_changes_content():
    ctx = await classify(TITLE, published=date(2026, 6, 8))
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.MISMATCHED


async def test_headline_only_text_and_photo_card_scope_get_the_same_content_result():
    text = await classify(TITLE.replace("১০", "২০"))
    card = await classify(TITLE.replace("১০", "২০"), scope=ClaimScope.HEADLINE_ONLY)
    assert text.claim_scope == card.claim_scope == ClaimScope.HEADLINE_ONLY
    assert text.content_status == card.content_status == ContentStatus.ALTERED
    assert text.analysis.content_check == card.analysis.content_check
    assert text.manipulation_flags.check_states["body"] == CheckState.NOT_APPLICABLE


async def test_headline_with_body_compares_the_body():
    ctx = await classify(TITLE, body=BODY)
    assert ctx.claim_scope == ClaimScope.HEADLINE_WITH_BODY
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.manipulation_flags.check_states["body"] == CheckState.PASSED
    assert any(f.part == "body" for f in ctx.analysis.content_check.findings)


async def test_content_check_makes_no_http_request(monkeypatch):
    forbidden = AsyncMock(side_effect=AssertionError("external call from content checking"))
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    status, _ = await status_of("কৃষকদের সহায়তায় ১০ কোটি টাকা দিল সরকার", model=nli(0.9, 0.02))
    assert status == ContentStatus.MATCHED
    forbidden.assert_not_awaited()


async def test_findings_survive_persistence_serialisation():
    details = AnalysisDetails(content_check=await compare(TITLE.replace("১০", "২০")))
    restored = AnalysisDetails.model_validate_json(details.model_dump_json())
    assert restored.content_check.findings[0].evidence[0].quote == TITLE


# ── helpers ──────────────────────────────────────────────────────────────


def test_quantities_bind_numbers_to_their_referent():
    values = quantities("দুর্ঘটনায় ৫জন নিহত ও ২০ জন আহত")
    assert [(q.value, q.role) for q in values] == [(5, "নিহত"), (20, "আহত")]
    assert quantities("সরকার ১০ লাখ টাকা বরাদ্দ দিয়েছে")[0].value == 1_000_000
    assert quantities("শুল্ক ১০ শতাংশ কমেছে")[0].value == 10
    assert quantities("৫০ হাজার কৃষক সহায়তা পাবেন")[0].noun == "কৃষক"


def test_statements_keep_the_last_sentence_and_abbreviations():
    spans = [s for _, _, s in split_statements("ড. ইউনূস বলেছেন। কর কমেনি।সবাই টাকা পেয়েছে")]
    assert spans == ["ড. ইউনূস বলেছেন।", "কর কমেনি।", "সবাই টাকা পেয়েছে"]
