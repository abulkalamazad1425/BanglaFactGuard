"""
app/pipelines/stages/s03_query_generator.py
=============================================
Stage 3: Search Query Generation

## Responsibility

Generate multiple diverse search query variants from the normalised claim
headline, body, and metadata. Diversity is critical: a single query often
misses the target article due to paraphrasing or transliteration differences.

## Query types generated

| Type             | Construction                              | Purpose                        |
|------------------|-------------------------------------------|--------------------------------|
| SITE_RESTRICTED  | site:domain + verbatim headline           | Exact site-scoped search       |
| HEADLINE         | Normalised headline verbatim              | Exact phrase match             |
| KEYWORDS         | Top-6 keywords from headline              | Keyword-based retrieval        |
| ENTITIES         | Headline + extracted NER entities         | Entity-anchored search         |
| DATE_BOUND       | Headline + formatted publication date     | Temporally constrained         |
| BODY_SUMMARY     | Top body keyphrases (if body present)    | Content-based fallback         |

## Key design for body-provided input

When the caller provides the full article body alongside the headline,
the body is the most reliable fingerprint. Body keywords are always extracted
and used as the primary BODY_SUMMARY query to maximise recall when the
exact headline phrasing is slightly off.

## Deduplication

Near-duplicate queries (differing only in whitespace/punctuation) are
deduplicated before being returned.

## Criticality: NON-CRITICAL
A minimum of 1 query (the raw headline) is always guaranteed.
"""

from __future__ import annotations

import structlog

from app.core.constants import MAX_SEARCH_QUERIES, PipelineStageID, QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.keyword_extractor import extract_body_keywords, extract_headline_keywords

logger = structlog.get_logger(__name__)

# Increase query cap so we do one site-restricted + full-headline
# + keyword + entity + date + body = up to 6 queries
_MAX_QUERIES = max(MAX_SEARCH_QUERIES, 6)


class QueryGeneratorStage:
    """
    Stage 3: Generate diverse search query variants from the normalised claim.

    No external dependencies — this is a pure transformation stage that
    uses only the keyword extractor utilities.
    """

    stage_id = PipelineStageID.S03_QUERY_GENERATOR

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Generate search query variants and store them in context.search_queries.

        Args:
            context: Pipeline context with normalized_headline, normalized_body,
                     and published_date set (by Stage 1).

        Returns:
            Context with search_queries populated as list of (query_text, query_type).

        Raises:
            QueryGenerationError: If no usable queries can be generated at all.
        """
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )

        queries: list[tuple[str, str]] = []  # (query_text, query_type_value)
        seen: set[str] = set()

        def _add_query(text: str, qtype: QueryType) -> None:
            """Deduplicate and add a query to the list."""
            normalised = text.strip()
            if normalised and normalised not in seen and len(queries) < _MAX_QUERIES:
                seen.add(normalised)
                queries.append((normalised, qtype.value))

        headline = context.normalized_headline
        domain = getattr(context, "normalized_source", None)

        # Extract headline keywords once — reused by multiple query types
        headline_keywords = extract_headline_keywords(headline, top_n=6)
        if headline_keywords:
            context.claim_keywords = headline_keywords

        # ------------------------------------------------------------------
        # Query 1: SITE_RESTRICTED — verbatim headline scoped to claimed domain
        # This is the single most important query when a source is provided.
        # ------------------------------------------------------------------
        if domain:
            _add_query(f"site:{domain} {headline}", QueryType.SITE_RESTRICTED)
        else:
            # No source provided — add the bare headline as SITE_RESTRICTED
            # (downstream providers will handle domain filtering themselves)
            _add_query(headline, QueryType.SITE_RESTRICTED)

        # ------------------------------------------------------------------
        # Query 2: HEADLINE — verbatim headline without site: operator
        # Lets providers that don't honour site: still search freely
        # ------------------------------------------------------------------
        _add_query(headline, QueryType.HEADLINE)

        # ------------------------------------------------------------------
        # Query 3: KEYWORDS — top keywords from headline
        # Short keyword queries work better on internal search and NewsData
        # ------------------------------------------------------------------
        if headline_keywords:
            keyword_query = " ".join(headline_keywords)
            _add_query(keyword_query, QueryType.KEYWORDS)

        # ------------------------------------------------------------------
        # Query 4: BODY_SUMMARY — top body keyphrases (if body present)
        # When the user provides the full article body, body keywords are the
        # most reliable fingerprint to find the exact original article.
        # This query is built BEFORE ENTITIES so it gets a priority slot.
        # ------------------------------------------------------------------
        if context.has_body and context.normalized_body:
            body_keywords = extract_body_keywords(context.normalized_body, top_n=8)
            if body_keywords:
                # Build a rich query: site:domain + top body keywords
                body_kw_str = " ".join(body_keywords[:5])
                if domain:
                    body_query = f"site:{domain} {body_kw_str}"
                else:
                    body_query = body_kw_str
                _add_query(body_query, QueryType.BODY_SUMMARY)

                # Also add a non-site-restricted body query as extra signal
                _add_query(" ".join(body_keywords[:5]), QueryType.BODY_SUMMARY)

        # ------------------------------------------------------------------
        # Query 5: ENTITIES — headline + pre-extracted entities
        # ------------------------------------------------------------------
        if context.claim_entities:
            entity_query = f"{headline} {' '.join(context.claim_entities[:3])}"
            _add_query(entity_query, QueryType.ENTITIES)
        else:
            if headline_keywords and len(headline_keywords) >= 2:
                # Use first two prominent keywords as entity proxy
                entity_query = f"{headline} {headline_keywords[0]} {headline_keywords[1]}"
                _add_query(entity_query, QueryType.ENTITIES)

        # ------------------------------------------------------------------
        # Query 6: DATE_BOUND — headline + publication date
        # ------------------------------------------------------------------
        if context.published_date:
            date_str = context.published_date.strftime("%Y %B %d").lstrip("0")
            date_query = f"{headline} {date_str}"
            _add_query(date_query, QueryType.DATE_BOUND)

        # ------------------------------------------------------------------
        # Validation: must have at least one query
        # ------------------------------------------------------------------
        if not queries:
            raise QueryGenerationError(
                stage_id=self.stage_id.value,
                message="No search queries could be generated from the claim.",
                details={
                    "headline": headline,
                    "has_body": context.has_body,
                },
            )

        context.search_queries = queries

        log.info(
            "queries_generated",
            count=len(queries),
            types=[q[1] for q in queries],
            has_body=context.has_body,
            domain=domain,
        )
        return context
