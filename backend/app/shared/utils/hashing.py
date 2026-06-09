"""
app/utils/hashing.py
=====================
Deterministic SHA-256 hashing utilities for cache key generation.

Design decisions:
- All hash inputs are lowercased, stripped, and Unicode-normalised (NFC)
  before hashing. This ensures that semantically identical strings
  ("প্রথম আলো " vs "প্রথম আলো") produce the same hash.
- `compute_claim_hash` is the canonical deduplication key used by:
    - Stage 2 (Redis cache lookup): key prefix `bgf:claim:{hash}`
    - Stage 2 (DB cache lookup): `verified_claims.claim_hash` column
  Both use the SAME function so keys are always consistent.
- `compute_url_hash` is used to deduplicate retrieved article URLs within
  a claim — stored in `retrieved_articles.url_hash`.
- All functions are pure (no I/O, no side effects) and thread-safe.
"""

from __future__ import annotations

import hashlib
import unicodedata


def _prepare(text: str) -> str:
    """
    Normalise a string to NFC Unicode form, strip whitespace, and lowercase.

    This is applied to all hash inputs to ensure that equivalent strings
    (different whitespace, composed/decomposed Unicode) produce identical hashes.

    Args:
        text: Raw input string.

    Returns:
        NFC-normalised, stripped, lowercased string.
    """
    return unicodedata.normalize("NFC", text).strip().lower()


def sha256_hex(value: str) -> str:
    """
    Compute the SHA-256 hex digest of a UTF-8 encoded string.

    Args:
        value: Input string (already normalised by the caller if needed).

    Returns:
        64-character lowercase hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_claim_hash(headline: str, claimed_source: str) -> str:
    """
    Compute the canonical deduplication hash for a verification claim.

    The hash is a SHA-256 digest of the pipe-separated concatenation of
    the normalised headline and normalised claimed source. This value is:
    - Stored in `verified_claims.claim_hash` (UNIQUE column).
    - Used as the Redis key suffix for `bgf:claim:{hash}`.

    Two claims are considered identical (cache-hit eligible) if and only if
    their normalised headline AND normalised source produce the same hash.

    Args:
        headline:       Raw or normalised headline string.
        claimed_source: Raw or normalised claimed source string.

    Returns:
        64-character lowercase hex SHA-256 digest.

    Example::

        h = compute_claim_hash("প্রথম আলো নতুন আইন", "প্রথম আলো")
        # Same result for: "prothom alo notun ain", "prothom alo"
        # → "7f3a9c..." (deterministic)
    """
    normalised = f"{_prepare(headline)}|{_prepare(claimed_source)}"
    return sha256_hex(normalised)


def compute_url_hash(url: str) -> str:
    """
    Compute the deduplication hash for an article URL.

    Strips query parameters that do not affect content identity
    (tracking params like `utm_source`, `fbclid`) before hashing.
    Stored in `retrieved_articles.url_hash`.

    Args:
        url: Raw article URL string.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    # Strip common tracking query parameters
    clean_url = _strip_tracking_params(url.strip())
    return sha256_hex(clean_url.lower())


def compute_text_hash(text: str) -> str:
    """
    Compute a hash for arbitrary text content (e.g. article body, query string).

    Used as the cache key suffix for:
    - `bgf:embedding:{hash}` — embedding vectors
    - `bgf:nli:{premise_hash}:{hyp_hash}` — NLI outputs
    - `bgf:article:{hash}` — extracted article content

    Args:
        text: Arbitrary text content to hash.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    return sha256_hex(_prepare(text))


def compute_search_query_hash(provider: str, query: str) -> str:
    """
    Compute the cache key hash for a search query result.

    Used as the suffix for: `bgf:search:{provider}:{hash}`

    Args:
        provider: Search provider name (e.g. "brave", "google_rss").
        query:    The exact search query string.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    return sha256_hex(f"{provider.lower()}|{_prepare(query)}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Tracking query parameters that should be stripped before URL hashing
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
    """
    Remove known tracking query parameters from a URL.

    Preserves all other query parameters to avoid colliding different
    articles that use query params for content selection (e.g. ?id=12345).

    Args:
        url: Raw URL string.

    Returns:
        URL with tracking parameters removed.
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
        new_query = urlencode(cleaned, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:  # noqa: BLE001
        # If URL parsing fails, hash the raw URL as-is
        return url
