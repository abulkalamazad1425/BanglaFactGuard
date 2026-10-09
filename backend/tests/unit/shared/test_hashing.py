"""Identity/cache hashes.

They are persisted (submissions.content_hash, retrieved_articles.url_hash)
and used as Redis keys, so the golden values guard against an accidental
change silently breaking reuse for every existing row. A deliberate change
(e.g. bumping VERIFICATION_PIPELINE_VERSION) must update them on purpose.
"""

from datetime import date

from app.core.constants import ClaimScope
from app.shared.utils.hashing import (
    compute_claim_hash,
    compute_search_query_hash,
    compute_text_hash,
    compute_url_hash,
)

HEADLINE = "ঢাকায় নতুন মেট্রোরেল চালু হয়েছে"
HO, HWB = ClaimScope.HEADLINE_ONLY, ClaimScope.HEADLINE_WITH_BODY


def test_golden_values():
    assert compute_claim_hash(HEADLINE, "prothomalo.com", HO) == (
        "6ee3582bb782b7bc6e68ca33b53dd0690c72fa75697e456a04388d875bd46ed6"
    )
    assert compute_claim_hash(
        HEADLINE, "prothomalo.com", HWB, body="আজ সকালে উদ্বোধন।", published_date=date(2026, 3, 15)
    ) == "095c502a3026bcbefeb8e97df662ff88b1406502d188c2cf5b5d7c7b0ee0d372"
    assert compute_url_hash("https://www.prothomalo.com/a/1?utm_source=fb&id=2") == (
        "0113b17a4eb968acf6c26cdbb091f40c14f3f5251a2309c1a937ab5254641f67"
    )
    assert compute_search_query_hash("py_google_news", "site:prothomalo.com মেট্রোরেল", date(2026, 3, 15)) == (
        "0cf354e4fa3b3a66e880513133b62bc7acbcfef4a7d6e289f2e88ee831d15edf"
    )
    assert compute_text_hash("Headline\nBody") == "e7ac7a8ec3ce8cd4811b8f1ca75991ff558fe1ed33397b4628e1181fedce39b1"


def test_every_identity_field_distinguishes_claims():
    base = dict(body="বডি এক", published_date=date(2026, 1, 1))
    h = compute_claim_hash(HEADLINE, "prothomalo.com", HWB, **base)
    assert len({
        h,
        compute_claim_hash(HEADLINE, "prothomalo.com", HWB, body="বডি দুই", published_date=date(2026, 1, 1)),
        compute_claim_hash(HEADLINE, "prothomalo.com", HWB, body="বডি এক", published_date=date(2026, 1, 2)),
        compute_claim_hash(HEADLINE, "prothomalo.com", HWB, body="বডি এক"),
        compute_claim_hash(HEADLINE, "jugantor.com", HWB, **base),
        compute_claim_hash(HEADLINE, "prothomalo.com", HWB, **base, version="v-old"),
        compute_claim_hash(HEADLINE, "prothomalo.com", HO, published_date=date(2026, 1, 1)),
    }) == 7


def test_identity_is_normalisation_stable_and_unambiguous():
    a = compute_claim_hash("  ঢাকায়  বৃষ্টি ​", "prothomalo.com", HO)
    assert a == compute_claim_hash("ঢাকায় বৃষ্টি", "prothomalo.com", HO)
    assert a == compute_claim_hash("ঢাকায় বৃষ্টি", "prothomalo.com", HO, body="ignored for headline-only")
    # structured serialisation: moving text between fields changes the hash
    assert compute_claim_hash("ক|খ", "গ", HO) != compute_claim_hash("ক", "খ|গ", HO)


def test_url_hash_ignores_tracking_params_and_case():
    assert compute_url_hash("https://www.prothomalo.com/a/1?utm_source=fb&fbclid=x&id=2") == compute_url_hash(
        "HTTPS://WWW.PROTHOMALO.COM/a/1?id=2"
    )
    assert compute_url_hash("https://a.com/x?id=1") != compute_url_hash("https://a.com/x?id=2")


def test_search_query_hash_depends_on_provider_query_and_date():
    q = "site:prothomalo.com মেট্রোরেল"
    assert compute_search_query_hash("PY_GOOGLE_NEWS", f"  {q} ") == compute_search_query_hash("py_google_news", q)
    assert compute_search_query_hash("internal_site", q) != compute_search_query_hash("py_google_news", q)
    assert compute_search_query_hash("p", q, date(2026, 1, 1)) != compute_search_query_hash("p", q)
