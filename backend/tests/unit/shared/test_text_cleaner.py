from app.shared.utils.text_cleaner import clean_extracted_text, clean_title, truncate_for_nli

PARAGRAPH = "সরকার আজ নতুন সেতুর উদ্বোধন করেছে এবং যান চলাচল শুরু হয়েছে।"


def test_extracted_text_loses_markup_boilerplate_and_extra_space():
    raw = (
        f"<p>{PARAGRAPH}</p>\n\n\n\n<div>আরও পড়ুন: অন্য খবর</div>\n"
        "১২:৩০\nAll rights reserved &amp; more\n  " + PARAGRAPH
    )
    text = clean_extracted_text(raw, min_length=10)
    assert "<" not in text and "আরও পড়ুন" not in text and "All rights reserved" not in text
    assert "১২:৩০" not in text  # short metadata line dropped
    assert "& more" in text and "\n\n\n" not in text
    assert text.count(PARAGRAPH) == 2


def test_too_short_or_empty_text_is_no_body():
    assert clean_extracted_text("ছোট লেখা", min_length=100) is None
    assert clean_extracted_text("") is None


def test_title_is_single_line_plain_text():
    assert clean_title("<b>ঢাকায়</b>\n  বৃষ্টি &amp; ঝড়") == "ঢাকায় বৃষ্টি & ঝড়"
    assert clean_title("  ") is None and clean_title(None) is None


def test_nli_truncation_prefers_a_sentence_boundary():
    text = "ক" * 70 + "। " + "খ" * 50
    assert truncate_for_nli(text, max_chars=100) == "ক" * 70 + "।"
    assert truncate_for_nli("ক" * 200, max_chars=100) == "ক" * 100  # no boundary: hard cut
    assert truncate_for_nli("short", max_chars=100) == "short"
