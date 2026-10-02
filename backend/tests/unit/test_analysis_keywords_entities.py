"""Keyword coverage, entity coverage and passage selection (acceptance
criteria 3, 5, 6, 7, 8) — deterministic, no models."""

from __future__ import annotations

from app.core.constants import MetricState
from app.features.verification.analysis.entities import (
    EntityMention,
    detect_role,
    entity_coverage,
    match_entity,
)
from app.features.verification.analysis.keywords import keyword_coverage
from app.features.verification.analysis.passages import select_relevant_passages
from app.features.verification.analysis.text import chunk_text, light_stem, tokenize

TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"


class TestKeywordCoverage:
    def test_identical_titles_give_complete_coverage(self):
        r = keyword_coverage(TITLE, TITLE)
        assert r.state == MetricState.COMPUTED
        assert r.value == 1.0
        assert r.unmatched == []

    def test_inflection_and_compound_differences_do_not_create_zero(self):
        # ঢাকায়/ঢাকা, সেতুর/সেতু and a split compound must still match.
        claim = "প্রধানমন্ত্রী ঢাকায় সেতুর উদ্বোধন"
        evidence = "প্রধান মন্ত্রী ঢাকা শহরে সেতু উদ্বোধন করেছেন"
        r = keyword_coverage(claim, evidence)
        assert r.state == MetricState.COMPUTED
        assert r.value == 1.0

    def test_genuine_zero_is_computed_zero_not_unavailable(self):
        r = keyword_coverage("ক্রিকেট বিশ্বকাপ জয়", "বন্যায় কৃষকের ফসল নষ্ট")
        assert r.state == MetricState.COMPUTED
        assert r.value == 0.0
        assert r.matched == []

    def test_empty_claim_is_empty_state(self):
        r = keyword_coverage("এবং ও", TITLE)
        assert r.state == MetricState.EMPTY
        assert r.value is None

    def test_missing_evidence_is_unavailable(self):
        r = keyword_coverage(TITLE, "")
        assert r.state == MetricState.UNAVAILABLE

    def test_extra_evidence_words_do_not_reduce_coverage(self):
        r = keyword_coverage(TITLE, TITLE + " বিকেলে বহু মানুষ উপস্থিত ছিলেন সংসদ সদস্যরাও এসেছিলেন")
        assert r.value == 1.0

    def test_negation_and_number_are_retained_and_weighted(self):
        claim = "সরকার ১০ জনকে নিয়োগ দেয়নি"
        units = {u.text: u for u in keyword_coverage(claim, claim).units}
        assert units["10"].kind == "number"
        assert any(u.kind == "negation" for u in units.values())
        # dropping the negation lowers coverage by its (higher) weight
        r = keyword_coverage(claim, "সরকার ১০ জনকে নিয়োগ দিয়েছে")
        assert r.value < 1.0
        assert "দেয়নি" in r.unmatched


class TestEntityCoverage:
    def test_all_claim_entities_present_plus_extra_article_entities_is_full(self):
        claim = [EntityMention("ঢাকা", "LOC"), EntityMention("শেখ হাসিনা", "PER")]
        evidence = [
            EntityMention("ঢাকা", "LOC"),
            EntityMention("শেখ হাসিনা", "PER"),
            EntityMention("খালেদা জিয়া", "PER"),
            EntityMention("চট্টগ্রাম", "LOC"),
            EntityMention("বিএনপি", "ORG"),
        ]
        cov = entity_coverage(claim, evidence, "ঢাকা শেখ হাসিনা খালেদা জিয়া চট্টগ্রাম", ner_available=True)
        assert cov.state == MetricState.COMPUTED
        assert cov.value == 1.0  # no penalty for the three extra article entities

    def test_missing_entities_are_listed(self):
        claim = [EntityMention("ঢাকা", "LOC"), EntityMention("রফিকুল ইসলাম", "PER")]
        evidence = [EntityMention("ঢাকা", "LOC")]
        cov = entity_coverage(claim, evidence, "ঢাকা", ner_available=True)
        assert cov.value == 0.5
        assert cov.unmatched == ["রফিকুল ইসলাম"]
        assert cov.matched == ["ঢাকা"]

    def test_no_claim_entities_is_not_applicable_not_100_percent(self):
        cov = entity_coverage([], [EntityMention("ঢাকা", "LOC")], "ঢাকা", ner_available=True)
        assert cov.state == MetricState.NOT_APPLICABLE
        assert cov.value is None

    def test_ner_failure_is_unavailable_not_zero_or_pass(self):
        cov = entity_coverage([EntityMention("ঢাকা", "LOC")], [], "ঢাকা", ner_available=False)
        assert cov.state == MetricState.UNAVAILABLE
        assert cov.value is None

    def test_inflected_surface_matches_bare_form(self):
        m = match_entity(EntityMention("ঢাকার", "LOC"), [EntityMention("ঢাকা", "LOC")], ())
        assert m.status == "exact"

    def test_alias_matches(self):
        m = match_entity(EntityMention("বাংলাদেশ জাতীয়তাবাদী দল", "ORG"), [EntityMention("বিএনপি", "ORG")], ())
        assert m.status == "alias"

    def test_shared_surname_does_not_merge_different_people(self):
        m = match_entity(
            EntityMention("রহমান", "PER"),
            [EntityMention("মুজিবুর রহমান", "PER"), EntityMention("জিয়াউর রহমান", "PER")],
            (),
        )
        assert m.status == "ambiguous"
        assert not m.matched

    def test_different_people_with_same_given_name_are_not_matched(self):
        m = match_entity(
            EntityMention("জিয়াউর রহমান", "PER"),
            [EntityMention("মুজিবুর রহমান", "PER")],
            tuple(light_stem(t) for t in tokenize("মুজিবুর রহমান")),
        )
        assert m.status in {"unmatched", "ambiguous"}
        assert not m.matched

    def test_multi_token_span_containment_matches(self):
        m = match_entity(
            EntityMention("মুহাম্মদ ইউনূস", "PER"),
            [EntityMention("ড. মুহাম্মদ ইউনূস", "PER")],
            (),
        )
        assert m.status == "span"

    def test_text_presence_when_evidence_ner_missed_it(self):
        cov = entity_coverage(
            [EntityMention("সিলেট", "LOC")], [], "বন্যায় সিলেট বিপর্যস্ত", ner_available=True
        )
        assert cov.value == 1.0

    def test_role_is_not_type(self):
        s = "আব্দুল করিম রফিককে মেরেছেন"
        assert detect_role(s, "রফিক") == "OBJECT"
        assert detect_role(s, "আব্দুল করিম") == "SUBJECT"


class TestPassages:
    BODY = (
        "সকালে বৃষ্টি হয়েছে। দুপুরে বাজারে ভিড় ছিল। "
        "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন। "
        "সেতুটি নির্মাণে তিন বছর সময় লেগেছে। "
        "এদিকে ক্রিকেট দল অনুশীলন করেছে। মাঠে আজ ম্যাচ নেই।"
    )

    def test_selects_relevant_sentences_with_context(self):
        ps = select_relevant_passages(TITLE, self.BODY)
        assert ps
        assert "উদ্বোধন" in ps[0].text
        assert "বাজারে ভিড়" in ps[0].text  # surrounding context sentence kept
        assert "ক্রিকেট" not in ps[0].text  # unrelated paragraph not pulled in

    def test_unrelated_body_yields_no_passages(self):
        assert select_relevant_passages(TITLE, "ক্রিকেট ম্যাচ হয়েছে মাঠে দর্শক ছিল প্রচুর।") == []

    def test_no_body_yields_nothing(self):
        assert select_relevant_passages(TITLE, None) == []


class TestChunking:
    def test_long_text_is_chunked_not_truncated(self):
        text = " ".join(f"বাক্য নম্বর {i} এখানে দেওয়া হলো।" for i in range(400))
        chunks, truncated = chunk_text(text, max_chars=300, max_chunks=500)
        assert not truncated
        assert all(len(c) <= 300 for c in chunks)
        assert "399" in chunks[-1]  # the tail survives

    def test_safety_cap_reports_truncation(self):
        text = " ".join(f"বাক্য {i} আছে এখানে।" for i in range(300))
        chunks, truncated = chunk_text(text, max_chars=60, max_chunks=5)
        assert truncated and len(chunks) == 5


class TestKeywordDefectRegression:
    """Confirmed root cause of the old zero keyword overlap: two independently
    selected top-N YAKE lists (6 unigrams vs 10 uni+bigrams of title+full body)
    compared with a symmetric Jaccard. An article that CONTAINS the identical
    title could still score 0."""

    BODY = " ".join(
        f"আজ বিকেলে আবহাওয়া অধিদপ্তর জানিয়েছে দেশের নদীর পানি বাড়ছে এবং তাপমাত্রা {i} ডিগ্রি থাকবে বন্যার আশঙ্কা রয়েছে কৃষকেরা উদ্বিগ্ন।"
        for i in range(30)
    ) + " প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন।"

    def test_old_independent_top_n_overlap_can_be_zero_for_a_matching_article(self):
        pytest = __import__("pytest")
        pytest.importorskip("yake")
        from app.shared.utils.keyword_extractor import (
            compute_weighted_keyword_overlap,
            extract_keywords_with_scores,
        )

        claim = extract_keywords_with_scores(TITLE, max_ngram_size=1, num_keywords=6)
        art = extract_keywords_with_scores(TITLE + " " + self.BODY, max_ngram_size=2, num_keywords=10)
        assert compute_weighted_keyword_overlap(claim, art) == 0.0  # the defect

    def test_coverage_checks_the_evidence_text_directly(self):
        assert keyword_coverage(TITLE, TITLE + " " + self.BODY).value == 1.0
