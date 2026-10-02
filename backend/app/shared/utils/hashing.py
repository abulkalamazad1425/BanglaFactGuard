from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from app.core.constants import ClaimScope


def _prepare(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canon_text(text: str | None) -> str:
    """The one text normalisation used for claim identity. Idempotent, so a
    caller may pass raw or already-normalised text and get the same hash."""
    from app.shared.utils.bangla_normalizer import normalize_bangla_text

    if not text:
        return ""
    return normalize_bangla_text(text).lower()


def claim_identity_payload(
    headline: str,
    claimed_source: str,
    claim_scope: "ClaimScope",
    *,
    body: str | None = None,
    published_date: "date | str | None" = None,
    version: str | None = None,
) -> dict:
    """The structured fields that make two verification runs interchangeable.

    A complete result may only be reused when every one of these is equal:
    normalised headline, normalised submitted body (only when the scope
    includes one), canonical claimed source, claimed publication date, claim
    scope, and the pipeline/model version.
    """
    from app.core.constants import VERIFICATION_PIPELINE_VERSION, ClaimScope

    with_body = claim_scope == ClaimScope.HEADLINE_WITH_BODY
    return {
        "v": version or VERIFICATION_PIPELINE_VERSION,
        "scope": claim_scope.value,
        "headline": _canon_text(headline),
        "body": _canon_text(body) if with_body else None,
        "source": _prepare(claimed_source),
        "date": (
            published_date.isoformat()
            if hasattr(published_date, "isoformat")
            else (str(published_date) if published_date else None)
        ),
    }


def compute_claim_hash(
    headline: str,
    claimed_source: str,
    claim_scope: "ClaimScope",
    *,
    body: str | None = None,
    published_date: "date | str | None" = None,
    version: str | None = None,
) -> str:
    """Identity of a claim for caching/deduplication — deterministic
    structured serialisation (sorted-key JSON), never ambiguous string
    concatenation. This is the single identity function: S01, the async
    registration path, S02 (Redis + DB), S12 write-back and the photo-card
    flow all call it."""
    payload = claim_identity_payload(
        headline,
        claimed_source,
        claim_scope,
        body=body,
        published_date=published_date,
        version=version,
    )
    return sha256_hex(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def compute_url_hash(url: str) -> str:

    clean_url = _strip_tracking_params(url.strip())
    return sha256_hex(clean_url.lower())


def compute_text_hash(text: str) -> str:
    return sha256_hex(_prepare(text))


def compute_search_query_hash(
    provider: str, query: str, published_date: "date | None" = None
) -> str:
    """Search-result cache key. The date is part of the key because a
    date-bound query is only valid for the date it was issued with."""
    return sha256_hex(
        json.dumps(
            {
                "p": provider.lower(),
                "q": _prepare(query),
                "d": published_date.isoformat() if published_date else None,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )


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
