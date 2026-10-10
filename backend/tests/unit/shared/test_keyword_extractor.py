from app.shared.utils import keyword_extractor as kx


def test_headline_keywords_are_content_words_and_short_text_has_none():
    keywords = kx.extract_headline_keywords("প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন", top_n=4)
    assert 0 < len(keywords) <= 4
    assert all(k not in kx.BANGLA_STOPWORDS for k in keywords)
    assert kx.extract_headline_keywords("ছোট") == []


def test_extractor_failure_falls_back_to_word_frequency(monkeypatch):
    def broken(*args):
        raise RuntimeError("yake failed")

    monkeypatch.setattr(kx, "_get_yake_extractor", broken)
    keywords = kx.extract_keywords_yake("বন্যা বন্যা বন্যা কৃষক কৃষক এবং ফসল।", num_keywords=2)
    assert keywords == ["বন্যা", "কৃষক"]  # most frequent first, stopwords dropped


def test_keyword_overlap_is_case_insensitive_jaccard():
    assert kx.compute_keyword_overlap(["Dhaka", "bridge"], ["dhaka ", "river"]) == 1 / 3
    assert kx.compute_keyword_overlap([], ["x"]) == 0.0
    assert kx.compute_keyword_overlap([], []) == 0.0
