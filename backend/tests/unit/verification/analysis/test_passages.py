from app.features.verification.analysis.passages import select_relevant_passages

TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"
BODY = (
    "সকালে বৃষ্টি হয়েছে। দুপুরে বাজারে ভিড় ছিল। "
    "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন। "
    "সেতুটি নির্মাণে তিন বছর সময় লেগেছে। "
    "এদিকে ক্রিকেট দল অনুশীলন করেছে। মাঠে আজ ম্যাচ নেই। "
    "পরে উপদেষ্টা ঢাকায় সেতুর পাশে বক্তব্য দেন।"
)


def test_relevant_sentences_are_selected_with_context_and_overlaps_merged():
    passages = select_relevant_passages(TITLE, BODY, max_passages=1)
    assert len(passages) == 1
    top = passages[0]
    assert top.score == 1.0 and "উদ্বোধন" in top.text
    assert "বাজারে ভিড়" in top.text and "তিন বছর" in top.text  # one sentence of context each side
    assert "ক্রিকেট" not in top.text and (top.first_sentence, top.last_sentence) == (1, 3)


def test_long_passages_are_capped():
    assert all(len(p.text) <= 40 for p in select_relevant_passages(TITLE, BODY, max_chars=40))


def test_nothing_relevant_or_nothing_to_read_gives_no_passages():
    assert select_relevant_passages(TITLE, "ক্রিকেট ম্যাচ হয়েছে মাঠে দর্শক ছিল প্রচুর।") == []
    assert select_relevant_passages(TITLE, None) == []
    assert select_relevant_passages("এবং ও", BODY) == []
