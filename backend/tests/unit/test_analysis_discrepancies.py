"""Concrete-discrepancy checks (acceptance 9, 11): every FAILED carries the
claim/evidence text that disagrees; low overlap alone never fails a check."""

from __future__ import annotations

from app.core.constants import CheckState
from app.features.verification.analysis.discrepancies import (
    EvidenceSentence,
    run_checks,
    sentences_of,
)
from app.features.verification.analysis.entities import EntityMention


def _run(claim, title, body="", claim_mentions=(), ev_mentions=(), ner=True, part="headline"):
    ev = [EvidenceSentence(title, "title")] + [
        EvidenceSentence(s, "body") for s in (body.split("।") if body else []) if s.strip()
    ]
    return run_checks(
        sentences_of(claim, part), ev, list(claim_mentions), list(ev_mentions), ner_available=ner
    )


def test_identical_headline_passes_applicable_checks_and_marks_rest_not_applicable():
    t = "বন্যায় ঢাকা শহরে সরকার ত্রাণ বিতরণ করেছে"
    r = _run(t, t)
    assert r["numbers"].state == CheckState.NOT_APPLICABLE
    assert r["negation"].state == CheckState.PASSED
    assert r["modality"].state == CheckState.PASSED
    assert r["scope"].state == CheckState.NOT_APPLICABLE
    assert r["attribution"].state == CheckState.NOT_APPLICABLE
    assert not any(c.discrepancies for c in r.values())


def test_changed_number_is_a_concrete_discrepancy():
    r = _run("বন্যায় ৫ জন নিহত হয়েছেন", "বন্যায় ১০ জন নিহত হয়েছেন")
    assert r["numbers"].state == CheckState.FAILED
    d = r["numbers"].discrepancies[0]
    assert "5" in d.detail and "10" in d.detail
    assert "১০" in d.evidence_text


def test_same_number_in_bangla_and_ascii_digits_and_words_matches():
    r = _run("বন্যায় 10 জন নিহত হয়েছেন", "বন্যায় ১০ জন নিহত হয়েছেন")
    assert r["numbers"].state == CheckState.PASSED
    r = _run("বন্যায় ৫ জন নিহত হয়েছেন", "বন্যায় পাঁচ জন নিহত হয়েছেন")
    assert r["numbers"].state == CheckState.PASSED


def test_magnitude_words_fold_into_value():
    r = _run("সরকার ১০ লাখ টাকা বরাদ্দ দিয়েছে", "সরকার ১০ লাখ টাকা বরাদ্দ দিয়েছে")
    assert r["numbers"].state == CheckState.PASSED
    r = _run("সরকার ১০ হাজার টাকা বরাদ্দ দিয়েছে", "সরকার ১০ লাখ টাকা বরাদ্দ দিয়েছে")
    assert r["numbers"].state == CheckState.FAILED


def test_unsupported_number_is_not_evaluated_not_failed():
    # source states no comparable number: unsupported, not contradicted
    r = _run("বন্যায় ৫ জন নিহত হয়েছেন", "বন্যায় বহু মানুষ নিহত হয়েছেন")
    assert r["numbers"].state == CheckState.NOT_EVALUATED


def test_flipped_negation_is_a_discrepancy():
    r = _run("সরকার শুল্ক কমায়নি", "সরকার শুল্ক কমিয়েছে")
    assert r["negation"].state == CheckState.FAILED
    assert "negates" in r["negation"].discrepancies[0].detail


def test_scope_change_universal_vs_partial():
    r = _run("সকল শিক্ষার্থী বৃত্তি পেয়েছে", "কিছু শিক্ষার্থী বৃত্তি পেয়েছে")
    assert r["scope"].state == CheckState.FAILED


def test_attribution_change():
    r = _run(
        "মন্ত্রী বলেছেন বন্যার ক্ষয়ক্ষতি ব্যাপক",
        "বিশেষজ্ঞ বলেছেন বন্যার ক্ষয়ক্ষতি ব্যাপক",
    )
    assert r["attribution"].state == CheckState.FAILED


def test_plan_reported_as_completed_event():
    r = _run("সরকার নতুন কর আরোপ করেছে", "সরকার নতুন কর আরোপের পরিকল্পনা করছে")
    assert r["modality"].state == CheckState.FAILED
    assert "completed" in r["modality"].discrepancies[0].detail


def test_entity_role_swap():
    claim = "আব্দুল করিম রফিককে মেরেছেন"
    title = "রফিক আব্দুল করিমকে মেরেছেন"
    ms = [EntityMention("আব্দুল করিম", "PER"), EntityMention("রফিক", "PER")]
    r = _run(claim, title, claim_mentions=ms, ev_mentions=ms)
    assert r["entities"].state == CheckState.FAILED
    assert r["entities"].discrepancies[0].kind == "entity_role"


def test_same_type_same_role_entity_substitution():
    r = _run(
        "রহিম মিরপুরে গ্রেপ্তার হয়েছেন",
        "করিম মিরপুরে গ্রেপ্তার হয়েছেন",
        claim_mentions=[EntityMention("রহিম", "PER"), EntityMention("মিরপুর", "LOC")],
        ev_mentions=[EntityMention("করিম", "PER"), EntityMention("মিরপুর", "LOC")],
    )
    assert r["entities"].state == CheckState.FAILED
    d = r["entities"].discrepancies[0]
    assert d.kind == "entity_substitution" and "করিম" in d.detail


def test_missing_entity_without_same_role_candidate_is_not_a_substitution():
    # Low entity overlap alone must not be declared a substitution.
    r = _run(
        "রহিম মিরপুরে গ্রেপ্তার হয়েছেন",
        "মিরপুরে একজন গ্রেপ্তার হয়েছেন",
        claim_mentions=[EntityMention("রহিম", "PER"), EntityMention("মিরপুর", "LOC")],
        ev_mentions=[EntityMention("মিরপুর", "LOC")],
    )
    assert r["entities"].state == CheckState.PASSED


def test_same_type_different_role_is_not_a_substitution():
    # PER "করিম" is the OBJECT in the source; "রহিম" is the SUBJECT in the claim.
    r = _run(
        "রহিম পুলিশকে ডেকেছেন",
        "পুলিশ করিমকে ডেকেছেন",
        claim_mentions=[EntityMention("রহিম", "PER")],
        ev_mentions=[EntityMention("করিম", "PER")],
    )
    assert r["entities"].state != CheckState.FAILED


def test_ner_unavailable_is_not_evaluated_never_passed():
    r = _run("রহিম মিরপুরে গ্রেপ্তার", "করিম মিরপুরে গ্রেপ্তার", ner=False)
    assert r["entities"].state == CheckState.NOT_EVALUATED


def test_unaligned_claim_is_not_evaluated_not_altered():
    r = _run("ক্রিকেট বিশ্বকাপে বাংলাদেশ জিতেছে", "বন্যায় কৃষকের ফসল নষ্ট হয়েছে")
    for name in ("negation", "modality", "scope"):
        assert r[name].state == CheckState.NOT_EVALUATED
    assert not any(c.discrepancies for c in r.values())


def test_body_discrepancy_is_labelled_body_part():
    title = "সরকার নতুন সেতু উদ্বোধন করেছে"
    body = "সেতু নির্মাণে ৫০০ কোটি টাকা ব্যয় হয়েছে।"
    # headline identical to the source title, but the submitted body changes the cost
    ev = [EvidenceSentence(title, "title"), EvidenceSentence(body.rstrip("।"), "body")]
    claim = sentences_of(title, "headline") + sentences_of("সেতু নির্মাণে ৯০০ কোটি টাকা ব্যয় হয়েছে।", "body")
    r = run_checks(claim, ev, [], [], ner_available=True)
    assert r["numbers"].state == CheckState.FAILED
    assert {d.part for d in r["numbers"].discrepancies} == {"body"}
