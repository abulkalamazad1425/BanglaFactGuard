"""Deterministic, quotable meaning changes between a headline and a title.
Each rule must fire on its change and stay silent on look-alikes."""

import pytest

from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.material_differences import (
    find_material_differences,
    modality,
    polarity,
    quantities,
    same_word_sequence,
    unmatched_content,
)


def kinds(claim: str, source: str, **kw) -> set[str]:
    return {d.kind for d in find_material_differences(claim, source, **kw)}


@pytest.mark.parametrize("claim,title,kind", [
    ("সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত", "numbers"),
    ("সড়ক দুর্ঘটনায় ৫ জন নিহত", "সড়ক দুর্ঘটনায় নিহত বেড়েছে", "numbers"),
    ("সরকার জ্বালানি তেলের দাম বাড়ায়নি", "সরকার জ্বালানি তেলের দাম বাড়িয়েছে", "negation"),
    ("পুলিশকে মারধর করল শিক্ষার্থীরা", "শিক্ষার্থীদের মারধর করল পুলিশ", "subject_object"),
    ("নির্বাচন হবে ডিসেম্বরে", "নির্বাচন হবে ফেব্রুয়ারিতে", "date"),
    ("আজ নির্বাচন কমিশনের বৈঠক", "নির্বাচন কমিশনের বৈঠক", "date"),
    ("মন্ত্রী দুর্নীতি করেছেন", "মন্ত্রী দুর্নীতি করেছেন বলে অভিযোগ বিরোধী দলের", "attribution"),
    ("সরকার নতুন সেতু উদ্বোধন করেছে", "সরকার নতুন সেতু উদ্বোধন করবে", "modality"),
    ("সব শিক্ষার্থী পরীক্ষায় পাস করেছে", "কিছু শিক্ষার্থী পরীক্ষায় পাস করেছে", "scope"),
    ("স্কুল বন্ধ থাকবে কাল", "স্কুল বন্ধ থাকবে কাল - খবরটি গুজব", "denial"),
])
def test_each_rule_fires_with_quoted_evidence(claim, title, kind):
    diffs = find_material_differences(claim, title)
    assert kind in {d.kind for d in diffs}
    assert all(d.claim_text and d.source_text and d.detail for d in diffs)


@pytest.mark.parametrize("claim,title", [
    ("সড়ক দুর্ঘটনায় পাঁচ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত"),            # same value, other spelling
    ("বাজেটে ১০০ কোটি টাকা বরাদ্দ", "বাজেটে ১০০ কোটি টাকা বরাদ্দ দিল সরকার"),
    ("শিক্ষার্থীদের দাবি মেনে নিল সরকার", "শিক্ষার্থীদের দাবি মেনে নিল সরকার"),  # দাবি = demand, not a claim frame
    ("সে আসবে কি না জানা যায়নি", "সে আসবে কি না জানা যায়নি"),
    ("ঢাকায় ভালোভাবে বৃষ্টি হয়েছে", "ঢাকায় ভারী বৃষ্টি হয়েছে"),                 # ভালোভাবে is not a future verb
])
def test_no_rule_fires_on_lookalikes(claim, title):
    assert kinds(claim, title) == set()


def test_entity_rules_need_usable_ner():
    sakib, tamim = EntityMention("সাকিব আল হাসান", "PER"), EntityMention("তামিম ইকবাল", "PER")
    claim, title = "সাকিব আল হাসান অবসরের ঘোষণা দিলেন", "তামিম ইকবাল অবসরের ঘোষণা দিলেন"
    [diff] = find_material_differences(claim, title, claim_mentions=[sakib], source_mentions=[tamim], ner_available=True)
    assert diff.kind == "entity" and diff.claim_text == sakib.text and diff.source_text == tamim.text
    [extra] = find_material_differences(claim, "অবসরের ঘোষণা দিলেন", claim_mentions=[sakib], ner_available=True)
    assert extra.kind == "entity" and "does not mention" in extra.detail
    assert kinds(claim, title, claim_mentions=[sakib], source_mentions=[tamim], ner_available=False) == set()


def test_building_blocks():
    [q] = quantities("২০ শতাংশ মূল্যস্ফীতি")
    assert (q.value, q.unit, q.role) == (20.0, "শতাংশ", "মূল্যস্ফীতি")
    assert quantities("৫ লাখ টাকা জরিমানা")[0].value == 500_000
    assert polarity("সে আসেনি") and not polarity("সে আসেনি না")  # double negation
    assert modality("সেতু উদ্বোধন হতে পারে") == "NOT_COMPLETED" and modality("সেতু উদ্বোধন হয়েছে") == "COMPLETED"
    assert modality("ঢাকার সেতু") == "UNKNOWN"
    assert same_word_sequence("‘মেসি’, রোনালদো!", "মেসি রোনালদো") and not same_word_sequence("", "")
    assert unmatched_content("ঢাকায় নতুন সেতু", "ঢাকার সেতু") == ["নতুন"]
