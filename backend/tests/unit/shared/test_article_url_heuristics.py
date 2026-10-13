import pytest

from app.shared.utils.article_url_heuristics import is_probable_article


@pytest.mark.parametrize("url,patterns,expected", [
    ("https://www.prothomalo.com/tag/dhaka", [r"prothomalo\.com/"], False),
    ("https://www.prothomalo.com/feed", None, False),
    ("https://www.prothomalo.com/search?q=x", None, False),
    ("https://www.prothomalo.com/archive/2026-01-01", None, False),
    ("https://www.prothomalo.com/bangladesh/story", [r"/bangladesh/"], True),
    ("https://samakal.com/national/2026/10/05/story", None, True),
    ("https://www.jugantor.com/national/123456", [r"/never/"], True),
    ("https://www.thedailystar.net/news/article-12345", None, True),
    ("https://www.prothomalo.com/bangladesh/district/abc12345def", None, True),
    ("https://www.prothomalo.com/bangladesh/politics", None, False),
])
def test_article_url_classification(url, patterns, expected):
    assert is_probable_article(url, patterns) is expected
