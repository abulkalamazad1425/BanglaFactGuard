"""Golden values for every identity/cache hash.

These hashes are persisted (submissions.content_hash, retrieved_articles.url_hash)
and used as Redis keys, so an accidental change silently breaks result reuse
and caching for every existing row. A deliberate change (e.g. bumping
VERIFICATION_PIPELINE_VERSION) must update these values on purpose.
"""

from datetime import date

from app.core.constants import ClaimScope
from app.features.photocard.verification_stages import compute_photocard_hash
from app.shared.utils.hashing import (
    compute_claim_hash,
    compute_search_query_hash,
    compute_text_hash,
    compute_url_hash,
)

HEADLINE = "ঢাকায় নতুন মেট্রোরেল চালু হয়েছে"


def test_claim_hash_headline_only():
    assert compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_ONLY) == (
        "6ee3582bb782b7bc6e68ca33b53dd0690c72fa75697e456a04388d875bd46ed6"
    )


def test_claim_hash_with_body_and_date():
    assert compute_claim_hash(
        HEADLINE,
        "prothomalo.com",
        ClaimScope.HEADLINE_WITH_BODY,
        body="আজ সকালে উদ্বোধন।",
        published_date=date(2026, 3, 15),
    ) == "095c502a3026bcbefeb8e97df662ff88b1406502d188c2cf5b5d7c7b0ee0d372"


def test_photocard_hash_with_date():
    assert compute_photocard_hash(HEADLINE, "prothomalo.com", published_date=date(2026, 3, 15)) == (
        "ad92cd767da07cf1cfe707c846f9e86dac0606e6673af009df85ab2ea512aae9"
    )


def test_photocard_hash_without_date():
    assert compute_photocard_hash(HEADLINE, "prothomalo.com") == (
        "ed052df03ae8bffaaad082c0045b9b4b8646fc8004303df00e7500997944655e"
    )


def test_url_hash_strips_tracking_params():
    assert compute_url_hash("https://www.prothomalo.com/a/1?utm_source=fb&id=2") == (
        "0113b17a4eb968acf6c26cdbb091f40c14f3f5251a2309c1a937ab5254641f67"
    )


def test_search_query_hash():
    assert compute_search_query_hash(
        "py_google_news", "site:prothomalo.com মেট্রোরেল", date(2026, 3, 15)
    ) == "0cf354e4fa3b3a66e880513133b62bc7acbcfef4a7d6e289f2e88ee831d15edf"


def test_text_hash():
    assert compute_text_hash("Headline\nBody") == (
        "e7ac7a8ec3ce8cd4811b8f1ca75991ff558fe1ed33397b4628e1181fedce39b1"
    )
