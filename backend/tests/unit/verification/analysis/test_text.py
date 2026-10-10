from app.features.verification.analysis.text import (
    chunk_text,
    content_tokens,
    is_negation_token,
    light_stem,
    normalize_for_match,
    split_sentences,
    tokenize,
)


def test_normalisation_unifies_digits_case_and_tokenizer_artifacts():
    assert normalize_for_match("  ঢাকায়▁১০  DHAKA। ") == "ঢাকায় 10 dhaka."
    assert tokenize("সড়কে ১০.৫ শতাংশ, Dhaka!") == ["সড়কে", "10.5", "শতাংশ", "dhaka"]


def test_light_stem_strips_inflections_but_keeps_a_minimum_stem():
    assert light_stem("সেতুর") == "সেতু"
    assert light_stem("শিক্ষার্থীদের") == "শিক্ষার্থী"
    assert light_stem("ঢাকায়") == "ঢাকা"
    assert light_stem("কে") == "কে"  # too short to strip


def test_negation_detection_includes_fused_forms_but_not_lookalike_nouns():
    assert is_negation_token("না") and is_negation_token("দেয়নি") and is_negation_token("করেনি")
    assert not is_negation_token("খনি") and not is_negation_token("ধ্বনি")


def test_content_tokens_drop_stopwords_but_keep_meaning_bearing_words():
    assert content_tokens("সরকার এবং সব ১০ জনকে নিয়োগ দেয়নি") == ["সরকার", "সব", "10", "জনকে", "নিয়োগ", "দেয়নি"]


def test_sentences_and_chunks_never_lose_text():
    assert split_sentences("প্রথম বাক্যটি এখানে। দ্বিতীয় বাক্যটি এখানে! ছোট।") == [
        "প্রথম বাক্যটি এখানে।", "দ্বিতীয় বাক্যটি এখানে!",
    ]
    text = " ".join(f"বাক্য নম্বর {i} এখানে দেওয়া হলো।" for i in range(400))
    chunks, truncated = chunk_text(text, max_chars=300, max_chunks=500)
    assert not truncated and all(len(c) <= 300 for c in chunks) and "399" in chunks[-1]
    # one over-long sentence is split on whitespace, not dropped
    long_sentence = " ".join(["শব্দ"] * 200)
    chunks, _ = chunk_text(long_sentence, max_chars=100)
    assert " ".join(chunks) == long_sentence
    # the safety cap is reported
    chunks, truncated = chunk_text(text, max_chars=60, max_chunks=5)
    assert truncated and len(chunks) == 5
