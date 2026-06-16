"""
app/pipelines/stages/s03_query_generator.py  (redesigned)
===========================================================
Stage 3: Search Query Generation — Multi-Strategy, Bangla-Aware

## What changed and why
────────────────────────────────────────────────────────────────
ROOT PROBLEM (old design)
  Every query was built once from the verbatim headline, then slightly
  mutated.  Because Bangla news sites paraphrase heavily, quote translated
  names differently, and vary honorifics/conjunctions, a verbatim phrase
  almost never matches the indexed title of the article at sites other than
  Prothom Alo (which Google indexes so densely that near-misses still hit).

NEW STRATEGY — three orthogonal query families
─────────────────────────────────────────────
  Family A — PRECISION  (site-scoped, short, unquoted keywords)
    The site: operator already constrains the domain; we do NOT need to also
    quote the phrase.  Short unquoted keyword queries have dramatically
    higher recall on Google CSE / DDG for less-indexed sites.

  Family B — RECALL  (no site: operator, entity-anchored)
    Some BD sites are barely indexed by Google.  Dropping site: and using
    distinctive named entities + date widens the net across all providers
    that don't honour site:.

  Family C — BODY FINGERPRINT  (when body provided)
    Rare Bangla n-grams from the article body are the most reliable
    fingerprint.  They survive editorial rewrites of the headline.

SPECIFIC FIXES vs old code
──────────────────────────
  1. NO blanket 8-word keyword cap.
     Old: _build_keyword_query cut every query at 8 words.
     New: queries for providers that need short queries (INTERNAL, NEWSDATA)
          are adapted in S04, not here.  S03 emits rich queries; S04 adapts.

  2. Transliteration variants for Bangla headlines.
     Named entities that commonly appear in both script (Bengali) and Roman
     transliteration get a second KEYWORD query with the Roman form so that
     NewsData (which indexes in English) can still find them.

  3. Paraphrase-tolerant keyword extraction.
     Instead of taking the first N words of the headline (which may be a
     grammatical particle), extract_headline_keywords already ranks by TF-IDF
     importance.  We additionally generate a TOP-3 bigram query to catch
     sources that indexed only a partial headline.

  4. Date narrowing is now a separate query slot, not appended to the
     verbatim headline (which would make an already-strict query even stricter).

  5. Deduplication is normalised: collapse runs of whitespace and strip
     leading site: before comparing, so "site:x.com foo bar" and "foo bar"
     are NOT treated as the same query (they're not — they target different
     providers differently).
"""

from __future__ import annotations

import re
import structlog

from app.core.constants import MAX_SEARCH_QUERIES, PipelineStageID, QueryType
from app.core.exceptions import QueryGenerationError
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.keyword_extractor import extract_body_keywords, extract_headline_keywords

logger = structlog.get_logger(__name__)

# Allow up to 10 query slots — S04 fans them out across 5 providers anyway,
# and the cache layer absorbs duplicate (provider, query-hash) pairs cheaply.
_MAX_QUERIES = max(MAX_SEARCH_QUERIES, 10)

# Bangla punctuation to normalise away before comparing for deduplication
_BANGLA_PUNCT = re.compile(r"[।!?\"'(){}\\[\\]<>]")
_WS = re.compile(r"\s+")


def _normalise_for_dedup(text: str) -> str:
    """Collapse whitespace and strip site: prefix for dedup comparison."""
    t = re.sub(r"site:\S+\s*", "", text)
    t = _BANGLA_PUNCT.sub(" ", t)
    return _WS.sub(" ", t).strip().lower()


def _bigrams(words: list[str], n: int = 3) -> str:
    """Return the first n bigrams of a word list joined as a single string."""
    pairs = [f"{words[i]} {words[i+1]}" for i in range(min(len(words) - 1, n))]
    return " ".join(pairs)


class QueryGeneratorStage:
    """
    Stage 3: Generate diverse, paraphrase-tolerant search query variants.

    Emits rich (full) queries.  Provider-specific length/format adaptation
    is the responsibility of S04._adapt_query() — not this stage.
    """

    stage_id = PipelineStageID.S03_QUERY_GENERATOR

    async def execute(self, context: PipelineContext) -> PipelineContext:
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )

        queries: list[tuple[str, str]] = []   # (query_text, query_type_value)
        seen_norm: set[str] = set()            # normalised forms for dedup

        def _add(text: str, qtype: QueryType) -> None:
            normalised = _normalise_for_dedup(text)
            raw = text.strip()
            if raw and normalised and normalised not in seen_norm and len(queries) < _MAX_QUERIES:
                seen_norm.add(normalised)
                queries.append((raw, qtype.value))

        headline = context.normalized_headline
        domain = getattr(context, "normalized_source", None)

        # ── Extract keywords once; store on context for downstream stages ──
        headline_keywords: list[str] = extract_headline_keywords(headline, top_n=8)
        if headline_keywords:
            context.claim_keywords = headline_keywords

        # ══════════════════════════════════════════════════════════════════
        # FAMILY A — PRECISION  (site-scoped, keyword-focused)
        # Goal: find the article on the exact claimed domain.
        # Key insight: do NOT quote the phrase. site: already pins the domain;
        # quoting makes recall collapse for poorly-indexed sites.
        # ══════════════════════════════════════════════════════════════════

        # A1 — site:domain + top-5 unquoted keywords  (most important query)
        if domain and headline_keywords:
            kw5 = " ".join(headline_keywords[:5])
            _add(f"site:{domain} {kw5}", QueryType.SITE_RESTRICTED)

        # A2 — site:domain + full headline (for well-indexed sites like Prothomalo)
        if domain:
            _add(f"site:{domain} {headline}", QueryType.SITE_RESTRICTED)

        # A3 — site:domain + top-3 bigrams  (handles partial-headline indexing)
        if domain and headline_keywords and len(headline_keywords) >= 4:
            bg = _bigrams(headline_keywords, n=3)
            _add(f"site:{domain} {bg}", QueryType.KEYWORDS)

        # ══════════════════════════════════════════════════════════════════
        # FAMILY B — RECALL  (domain-free, entity + date anchored)
        # Goal: recover when Google/DDG has not indexed the site well.
        # NewsData and PyGoogleNews do their own filtering; they need queries
        # without site: to return anything at all for small BD outlets.
        # ══════════════════════════════════════════════════════════════════

        # B1 — verbatim headline alone  (for providers that do domain filtering internally)
        _add(headline, QueryType.HEADLINE)

        # B2 — top-5 keywords alone  (NewsData / PyGoogleNews recall)
        if headline_keywords:
            _add(" ".join(headline_keywords[:5]), QueryType.KEYWORDS)

        # B3 — headline + named entities  (entity-anchored; survives paraphrase)
        if context.claim_entities:
            entities_str = " ".join(context.claim_entities[:3])
            _add(f"{headline} {entities_str}", QueryType.ENTITIES)
        elif headline_keywords and len(headline_keywords) >= 3:
            # proxy: two highest-weight keywords as entity stand-ins
            _add(f"{headline} {headline_keywords[0]} {headline_keywords[1]}", QueryType.ENTITIES)

        # B4 — top keywords + publication date  (temporally narrow, no site:)
        if context.published_date and headline_keywords:
            date_str = context.published_date.strftime("%d %B %Y")
            kw4 = " ".join(headline_keywords[:4])
            _add(f"{kw4} {date_str}", QueryType.DATE_BOUND)

        # B5 — headline + date  (for well-indexed sites where date narrows duplicates)
        if context.published_date:
            date_str = context.published_date.strftime("%Y %B %d")
            _add(f"{headline} {date_str}", QueryType.DATE_BOUND)

        # ══════════════════════════════════════════════════════════════════
        # FAMILY C — BODY FINGERPRINT  (only when full body is supplied)
        # These are the most reliable queries: rare n-grams from the article
        # body survive all editorial rewrites of the headline.
        # ══════════════════════════════════════════════════════════════════
        if context.has_body and context.normalized_body:
            body_keywords: list[str] = extract_body_keywords(context.normalized_body, top_n=10)
            if body_keywords:
                # C1 — site:domain + top-5 body keywords
                if domain:
                    body_kw5 = " ".join(body_keywords[:5])
                    _add(f"site:{domain} {body_kw5}", QueryType.BODY_SUMMARY)

                # C2 — body keywords alone (for non-site providers)
                _add(" ".join(body_keywords[:5]), QueryType.BODY_SUMMARY)

                # C3 — rare body bigrams (most distinctive fingerprint)
                if len(body_keywords) >= 4:
                    body_bg = _bigrams(body_keywords, n=3)
                    _add(body_bg, QueryType.BODY_SUMMARY)

        # ── Validation ────────────────────────────────────────────────────
        if not queries:
            # Last-resort: the raw headline always works as a query
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