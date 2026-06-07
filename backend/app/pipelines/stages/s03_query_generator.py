"""
app/pipelines/stages/s03_query_generator.py
=============================================
Stage 3: Search Query Generation

## Responsibility

Generate multiple diverse search query variants from the normalised claim
headline, body, and metadata. Diversity is critical: a single query often
misses the target article due to paraphrasing or transliteration differences.

## Query types generated

| Type         | Construction                              | Purpose                        |
|--------------|-------------------------------------------|--------------------------------|
| HEADLINE     | Normalised headline verbatim              | Exact phrase match             |
| KEYWORDS     | Top-6 keywords from headline              | Keyword-based retrieval        |
| ENTITIES     | Headline + extracted NER entities         | Entity-anchored search         |
| DATE_BOUND   | Headline + formatted publication date     | Temporally constrained         |
| BODY_SUMMARY | Top-8 body keyphrases (if body present)  | Content-based fallback         |

## Deduplication

Near-duplicate queries (differing only in whitespace/punctuation) are
deduplicated before being returned. The query list is capped at
`MAX_SEARCH_QUERIES` (5) from constants.py.

## Criticality: NON-CRITICAL
If query generation produces fewer than expected variants (e.g. no body
available), the pipeline continues with whatever queries were generated.
A minimum of 1 query (the raw headline) is always guaranteed.
"""

from __future__ import annotations

import structlog

from app.core.constants import MAX_SEARCH_QUERIES, PipelineStageID, QueryType
from app.core.exceptions import QueryGenerationError
from app.pipelines.context import PipelineContext
from app.utils.keyword_extractor import extract_body_keywords, extract_headline_keywords

logger = structlog.get_logger(__name__)


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
            if normalised and normalised not in seen and len(queries) < MAX_SEARCH_QUERIES:
                seen.add(normalised)
                queries.append((normalised, qtype.value))

        headline = context.normalized_headline

        # ------------------------------------------------------------------
        # Query 1: HEADLINE — verbatim normalised headline
        # ------------------------------------------------------------------
        _add_query(headline, QueryType.HEADLINE)

        # ------------------------------------------------------------------
        # Query 2: KEYWORDS — top keywords from headline
        # ------------------------------------------------------------------
        headline_keywords = extract_headline_keywords(headline, top_n=6)
        if headline_keywords:
            keyword_query = " ".join(headline_keywords)
            _add_query(keyword_query, QueryType.KEYWORDS)
            # Store in context for downstream stages (Stage 8)
            context.claim_keywords = headline_keywords

        # ------------------------------------------------------------------
        # Query 3: ENTITIES — headline + any pre-extracted entities
        # (Entities are populated later by NER in Stage 8, but if the
        #  normalised headline contains obvious entity tokens we include them)
        # ------------------------------------------------------------------
        if context.claim_entities:
            entity_query = f"{headline} {' '.join(context.claim_entities[:3])}"
            _add_query(entity_query, QueryType.ENTITIES)
        else:
            # Fall back to headline + first 2 keywords as entity proxy
            if headline_keywords:
                entity_query = f"{headline} {headline_keywords[0]}"
                _add_query(entity_query, QueryType.ENTITIES)

        # ------------------------------------------------------------------
        # Query 4: DATE_BOUND — headline + publication date
        # ------------------------------------------------------------------
        if context.published_date:
            date_str = context.published_date.strftime("%Y %B %d").lstrip("0")
            date_query = f"{headline} {date_str}"
            _add_query(date_query, QueryType.DATE_BOUND)

        # ------------------------------------------------------------------
        # Query 5: BODY_SUMMARY — top body keyphrases (if body present)
        # ------------------------------------------------------------------
        if context.has_body and context.normalized_body:
            body_keywords = extract_body_keywords(context.normalized_body, top_n=8)
            if body_keywords:
                # Combine top headline keyword with top body keywords
                top_headline_kw = headline_keywords[0] if headline_keywords else ""
                body_query_parts = [top_headline_kw] + body_keywords[:4]
                body_query = " ".join(p for p in body_query_parts if p)
                _add_query(body_query, QueryType.BODY_SUMMARY)

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
        )
        return context
