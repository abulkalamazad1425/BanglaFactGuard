"""Host allow-listing against a claimed source's registered domains/channels."""

from __future__ import annotations

from urllib.parse import urlparse


def _host(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" in value:
        value = urlparse(value).hostname or ""
    value = value.split("/")[0].split(":")[0]
    return value[4:] if value.startswith("www.") else value


def allowed_domains_for(normalized_source: str | None, source_config: dict | None) -> list[str]:
    """The canonical domain plus any other registered channel for the source
    (its base_url host and domain-looking aliases)."""
    domains: list[str] = []
    for candidate in [normalized_source, *(source_config or {}).get("allowed_domains", [])]:
        h = _host(candidate or "")
        if h and h not in domains:
            domains.append(h)
    return domains


def is_allowed_host(host: str, allowed: list[str]) -> bool:
    """True when `host` is, or is a subdomain of, an allowed domain."""
    h = _host(host)
    if not h:
        return False
    return any(h == d or h.endswith("." + d) for d in allowed)
