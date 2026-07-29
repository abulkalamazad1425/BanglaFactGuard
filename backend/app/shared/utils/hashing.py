
from __future__ import annotations

import hashlib
import unicodedata


def _prepare(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_claim_hash(headline: str, claimed_source: str) -> str:
    normalised = f"{_prepare(headline)}|{_prepare(claimed_source)}"
    return sha256_hex(normalised)


def compute_url_hash(url: str) -> str:

    clean_url = _strip_tracking_params(url.strip())
    return sha256_hex(clean_url.lower())


def compute_text_hash(text: str) -> str:
    return sha256_hex(_prepare(text))


def compute_search_query_hash(provider: str, query: str) -> str:
    return sha256_hex(f"{provider.lower()}|{_prepare(query)}")







_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "referrer",
        "_ga",
    }
)


def _strip_tracking_params(url: str) -> str:
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
        new_query = urlencode(cleaned, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:

        return url
