import pytest

from app.shared.utils.headline_preview import headline_preview


@pytest.mark.parametrize("headline,expected", [
    ("One two three four five six", "One two three four five..."),
    ("One two three four five", "One two three four five"),
    ("  ঢাকায়   আজ ভারী\tবৃষ্টি এখন  ", "ঢাকায় আজ ভারী বৃষ্টি এখন"),
    ("এক দুই তিন চার পাঁচ ছয়", "এক দুই তিন চার পাঁচ..."),
    ("   ", ""),
    (None, ""),
])
def test_headline_preview(headline, expected):
    assert headline_preview(headline) == expected
