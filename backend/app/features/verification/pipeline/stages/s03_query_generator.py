from __future__ import annotations

import re
import structlog

from app.core.constants import MAX_SEARCH_QUERIES, PipelineStageID, QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.keyword_extractor import (
    extract_body_keywords,
    extract_headline_keywords,
)

logger = structlog.get_logger(__name__)


_MAX_QUERIES = max(MAX_SEARCH_QUERIES, 10)


_BANGLA_PUNCT = re.compile(r"[।!?\"'(){}\\[\\]<>]")
_WS = re.compile(r"\s+")


def _normalise_for_dedup(text: str) -> str:
    t = re.sub(r"site:\S+\s*", "", text)
    t = _BANGLA_PUNCT.sub(" ", t)
    return _WS.sub(" ", t).strip().lower()


def _bigrams(words: list[str], n: int = 3) -> str:
    pairs = [f"{words[i]} {words[i+1]}" for i in range(min(len(words) - 1, n))]
    return " ".join(pairs)


class QueryGeneratorStage:

    stage_id = PipelineStageID.S03_QUERY_GENERATOR

    async def execute(self, context: PipelineContext) -> PipelineContext:
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )

        queries: list[tuple[str, str]] = []
        seen_norm: set[str] = set()

        def _add(text: str, qtype: QueryType) -> None:
            normalised = _normalise_for_dedup(text)
            raw = text.strip()
            if (
                raw
                and normalised
                and normalised not in seen_norm
                and len(queries) < _MAX_QUERIES
            ):
                seen_norm.add(normalised)
                queries.append((raw, qtype.value))

        headline = context.normalized_headline
        domain = getattr(context, "normalized_source", None)

        headline_keywords: list[str] = extract_headline_keywords(headline, top_n=8)
        if headline_keywords:
            context.claim_keywords = headline_keywords

        if domain and headline_keywords:
            kw5 = " ".join(headline_keywords[:5])
            _add(f"site:{domain} {kw5}", QueryType.SITE_RESTRICTED)

        if domain:
            _add(f"site:{domain} {headline}", QueryType.SITE_RESTRICTED)

        if domain and headline_keywords and len(headline_keywords) >= 4:
            bg = _bigrams(headline_keywords, n=3)
            _add(f"site:{domain} {bg}", QueryType.KEYWORDS)

        _add(headline, QueryType.HEADLINE)

        if headline_keywords:
            _add(" ".join(headline_keywords[:5]), QueryType.KEYWORDS)

        if context.claim_entities:
            entities_str = " ".join(context.claim_entities[:3])
            _add(f"{headline} {entities_str}", QueryType.ENTITIES)
        elif headline_keywords and len(headline_keywords) >= 3:

            _add(
                f"{headline} {headline_keywords[0]} {headline_keywords[1]}",
                QueryType.ENTITIES,
            )

        if context.published_date and headline_keywords:
            date_str = context.published_date.strftime("%d %B %Y")
            kw4 = " ".join(headline_keywords[:4])
            _add(f"{kw4} {date_str}", QueryType.DATE_BOUND)

        if context.published_date:
            date_str = context.published_date.strftime("%Y %B %d")
            _add(f"{headline} {date_str}", QueryType.DATE_BOUND)

        if context.has_body and context.normalized_body:
            body_keywords: list[str] = extract_body_keywords(
                context.normalized_body, top_n=10
            )
            if body_keywords:

                if domain:
                    body_kw5 = " ".join(body_keywords[:5])
                    _add(f"site:{domain} {body_kw5}", QueryType.BODY_SUMMARY)

                _add(" ".join(body_keywords[:5]), QueryType.BODY_SUMMARY)

                if len(body_keywords) >= 4:
                    body_bg = _bigrams(body_keywords, n=3)
                    _add(body_bg, QueryType.BODY_SUMMARY)

        if not queries:

            queries.append((headline, QueryType.HEADLINE.value))
            log.warning("s03_fallback_to_raw_headline", headline=headline[:80])

        if len(queries) < 2:
            raise QueryGenerationError(
                stage_id=self.stage_id.value,
                message="Too few search queries generated.",
                details={"headline": headline, "has_body": context.has_body},
            )

        context.search_queries = queries

        log.info(
            "s03_queries_generated",
            count=len(queries),
            types=[q[1] for q in queries],
            has_body=context.has_body,
            domain=domain,
        )
        return context
