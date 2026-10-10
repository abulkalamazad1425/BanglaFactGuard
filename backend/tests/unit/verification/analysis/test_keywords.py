"""Directional keyword coverage: are the claim's keywords in the evidence?"""

from app.core.constants import MetricState
from app.features.verification.analysis import keywords as kw
from app.features.verification.analysis.keywords import keyword_coverage

TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"


def test_identical_text_and_extra_evidence_words_give_complete_coverage():
    r = keyword_coverage(TITLE, TITLE + " বিকেলে বহু মানুষ উপস্থিত ছিলেন " * 30)
    assert (r.state, r.value, r.unmatched) == (MetricState.COMPUTED, 1.0, [])


def test_inflection_and_split_compounds_still_match():
    r = keyword_coverage("প্রধানমন্ত্রী ঢাকায় সেতুর উদ্বোধন", "প্রধান মন্ত্রী ঢাকা শহরে সেতু উদ্বোধন করেছেন")
    assert r.value == 1.0


def test_genuine_zero_is_computed_not_unavailable():
    r = keyword_coverage("ক্রিকেট বিশ্বকাপ জয়", "বন্যায় কৃষকের ফসল নষ্ট")
    assert (r.state, r.value, r.matched) == (MetricState.COMPUTED, 0.0, [])


def test_negation_and_numbers_are_weighted_units():
    claim = "সরকার ১০ জনকে নিয়োগ দেয়নি"
    units = {u.text: u.kind for u in keyword_coverage(claim, claim).units}
    assert units["10"] == "number" and units["দেয়নি"] == "negation"
    r = keyword_coverage(claim, "সরকার ১০ জনকে নিয়োগ দিয়েছে")
    assert r.unmatched == ["দেয়নি"] and r.value == 4.5 / 6  # numbers and negation weigh 1.5


def test_states_for_missing_input_and_failure(monkeypatch):
    assert keyword_coverage("এবং ও", TITLE).state == MetricState.EMPTY
    assert keyword_coverage(TITLE, "  ").state == MetricState.UNAVAILABLE

    def broken(_):
        raise ValueError("tokenizer failed")

    monkeypatch.setattr(kw, "evidence_keys", broken)
    failed = keyword_coverage(TITLE, TITLE)
    assert failed.state == MetricState.UNAVAILABLE and "keyword utility failed" in failed.reason
