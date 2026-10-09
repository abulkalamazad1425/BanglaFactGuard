from __future__ import annotations

import re

import structlog

from app.core.constants import MAX_SEARCH_QUERIES, PipelineStageID, QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.keyword_extractor import extract_headline_keywords

logger = structlog.get_logger(__name__)


class QueryGeneratorStage:
    """Headline, all-keyword, first-3 and first-4 keyword searches; the headline
    and all-keyword queries are repeated with the user date when one is given.

    Every query is restricted to the resolved source. Body text is used only
    for downstream content verification, never for evidence discovery.
    """

    stage_id = PipelineStageID.S03_QUERY_GENERATOR

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if context.is_verified_sources_mode:
            return self._verified_sources_queries(context)
        domain = context.normalized_source
        headline = context.normalized_headline.strip()
        if not domain or not headline:
            raise QueryGenerationError(
                stage_id=self.stage_id.value,
                message="A normalized headline and selected source are required for search.",
            )

        # Never interpret a site operator inside submitted text as a source.
        headline = re.sub(r"\bsite:\S+", "", headline, flags=re.IGNORECASE).strip()
        keywords = extract_headline_keywords(headline, top_n=8)
        context.claim_keywords = keywords
        keyword_text = " ".join(keywords)
        queries: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add(text: str, kind: QueryType) -> None:
            text = re.sub(r"\s+", " ", text).strip()
            key = text.casefold()
            if text and key not in seen and len(queries) < MAX_SEARCH_QUERIES:
                seen.add(key)
                queries.append((f"site:{domain} {text}", kind.value))

        add(headline, QueryType.HEADLINE)
        add(keyword_text, QueryType.KEYWORDS)
        # Shorter keyword queries (first 3 and first 4 keywords) when the
        # headline has that many; duplicates of the full set are dropped.
        for n in (3, 4):
            if len(keywords) >= n:
                add(" ".join(keywords[:n]), QueryType.KEYWORDS)
        if context.published_date:
            date_text = context.published_date.strftime("%d %B %Y")
            add(f"{headline} {date_text}", QueryType.DATE_BOUND)
            if keyword_text:
                add(f"{keyword_text} {date_text}", QueryType.DATE_BOUND)

        context.search_queries = queries
        logger.info(
            "s03_queries_generated",
            count=len(queries),
            domain=domain,
            types=[kind for _, kind in queries],
        )
        return context

    def _verified_sources_queries(self, context: PipelineContext) -> PipelineContext:
        """Bounded phrasings without a site operator: S04 runs each one once
        per group of verified domains (``site:a OR site:b ...``), never once
        per source."""
        from app.core.config import get_settings

        headline = re.sub(r"\bsite:\S+", "", context.normalized_headline.strip(), flags=re.IGNORECASE).strip()
        if not headline:
            raise QueryGenerationError(
                stage_id=self.stage_id.value, message="A normalized headline is required for search."
            )
        scope = context.verified_scope
        if scope is None or scope.empty:
            # No active verified source: nothing may be searched (never an
            # unrestricted web search). The result is INCOMPLETE.
            context.claim_keywords = extract_headline_keywords(headline, top_n=8)
            context.search_queries = []
            raise QueryGenerationError(
                stage_id=self.stage_id.value, message="No active verified sources are available to search."
            )
        limit = get_settings().search.fallback_max_queries
        keywords = extract_headline_keywords(headline, top_n=8)
        context.claim_keywords = keywords
        queries: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add(text: str, kind: QueryType) -> None:
            text = re.sub(r"\s+", " ", text).strip()
            key = text.casefold()
            if text and key not in seen and len(queries) < limit:
                seen.add(key)
                queries.append((text, kind.value))

        add(headline, QueryType.HEADLINE)
        add(" ".join(keywords), QueryType.KEYWORDS)
        if len(keywords) >= 4:
            add(" ".join(keywords[:4]), QueryType.KEYWORDS)
        context.search_queries = queries
        logger.info(
            "s03_verified_sources_queries_generated",
            count=len(queries),
            publishers=len(scope.publishers),
        )
        return context
