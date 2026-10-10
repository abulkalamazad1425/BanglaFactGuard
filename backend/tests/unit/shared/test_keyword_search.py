"""Query parsing for the application's list search. Ranking and filtering
against real rows are covered by the repositories/services that use it
(e.g. test_submission_repository.py)."""

from app.shared.utils.keyword_search import KeywordSearch, escape_like, spellings, split_keywords


def test_keywords_are_unique_meaningful_and_bounded():
    assert split_keywords("  ঢাকা   বাস দুর্ঘটনা ঢাকা ") == ["ঢাকা", "বাস", "দুর্ঘটনা"]
    assert split_keywords("The bus, and the CRASH! a 5") == ["bus", "CRASH", "5"]
    assert split_keywords("এবং ও") == []
    assert len(split_keywords(" ".join(f"শব্দ{i}" for i in range(20)))) == 8
    assert split_keywords(None) == []


def test_like_wildcards_are_escaped():
    assert escape_like("50%_a\\b") == "50\\%\\_a\\\\b"


def test_nukta_letters_are_searched_in_both_spellings():
    assert spellings("মোতায়েন") == ["মোতায়েন", "মোতায়েন"]
    assert spellings("ঢাকা") == ["ঢাকা"]


def test_a_stopword_only_query_still_searches_what_was_typed():
    search = KeywordSearch("এবং", columns=[])
    assert search.active and search.keywords == ["এবং"]
    blank = KeywordSearch("   ", columns=[])
    assert not blank.active and blank.condition is None and blank.order_by() == []
