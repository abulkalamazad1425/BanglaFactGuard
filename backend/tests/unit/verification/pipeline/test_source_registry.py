"""The seed snapshot of verified sources must be loadable as-is: every
record describes its own domain and its URL patterns compile."""

import re

from app.features.verification.pipeline.source_registry import (
    SOURCE_RECORD_METADATA,
    SOURCE_REGISTRY,
)
from app.shared.utils.domains import is_allowed_host


def test_every_record_is_consistent_and_usable():
    assert SOURCE_REGISTRY and set(SOURCE_RECORD_METADATA) == set(SOURCE_REGISTRY)
    for canonical, record in SOURCE_REGISTRY.items():
        assert canonical == canonical.lower().strip() and record["name"]
        assert is_allowed_host(record["base_url"], [canonical]), canonical
        for pattern in record.get("article_url_patterns") or []:
            re.compile(pattern)
        url = record.get("internal_search_url")
        assert url is None or "{query}" in url, canonical
