"""Deterministic stand-ins for the ML services, used by orchestration tests.

These fakes make stage logic testable; they say NOTHING about the accuracy of
LaBSE, the NER checkpoint or the NLI model. The "embedding" is a hashed
bag-of-stems vector, so identical text scores 1.0 and unrelated text ~0.
"""

from __future__ import annotations

import zlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import numpy as np

from app.core.constants import ClaimScope, SearchProvider
from app.features.articles.schemas import RankedArticleSchema
from app.features.nlp.ner_service import NERResult
from app.features.verification.analysis.content_check import ContentComparator
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.text import content_tokens, light_stem
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.features.verification.pipeline.stages.s08_similarity_analyzer import (
    SimilarityAnalyzerStage,
)
from app.features.verification.pipeline.stages.s09_contradiction_detector import (
    ContradictionDetectorStage,
)
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.schemas import NLIScoresSchema

DIM = 512


class FakeEmbedder:
    def __init__(self) -> None:
        self.similarity_calls: list[tuple[str, str]] = []
        self.batch_calls: list[list[str]] = []

    @staticmethod
    def _vec(text: str) -> np.ndarray:
        v = np.zeros(DIM, dtype=np.float32)
        for tok in content_tokens(text):
            v[zlib.crc32(light_stem(tok).encode()) % DIM] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    async def encode_batch(self, texts):
        self.batch_calls.append(list(texts))
        return [self._vec(t) for t in texts]

    async def compute_similarity(self, a: str, b: str) -> float:
        self.similarity_calls.append((a, b))
        return max(0.0, min(1.0, float(np.dot(self._vec(a), self._vec(b)))))


class FakeNER:
    """Detects any of `known` whose text occurs in the input."""

    def __init__(self, known: list[EntityMention] | None = None, *, available: bool = True) -> None:
        self.known = known or []
        self.available = available

    async def extract_mentions(self, text: str) -> NERResult:
        if not self.available:
            return NERResult(False, error="down")
        return NERResult(True, [m for m in self.known if m.text in text])


def neutral_nli() -> MagicMock:
    nli = MagicMock()
    nli.predict = AsyncMock(
        return_value=NLIScoresSchema(entailment=0.3, contradiction=0.1, neutral=0.6)
    )
    return nli


def article(
    title: str,
    body: str | None = None,
    *,
    published: date | None = date(2026, 6, 7),
    url: str = "https://prothomalo.com/article/1",
) -> RankedArticleSchema:
    return RankedArticleSchema(
        url=url,
        title=title,
        body=body,
        published_date=published,
        published_date_source="json_ld.datePublished" if published else None,
        rank_score=0.9,
        search_provider=SearchProvider.INTERNAL_SITE,
    )


def make_context(
    headline: str,
    *,
    body: str | None = None,
    scope: ClaimScope | None = None,
    published_date: date | None = None,
    top: RankedArticleSchema | None = None,
    search_adequate: bool | None = True,
) -> PipelineContext:
    ctx = build_context(
        headline=headline,
        claimed_source="prothomalo.com",
        news_body=body if scope != ClaimScope.HEADLINE_ONLY else None,
        published_date=published_date,
        claim_scope=scope,
    )
    ctx.normalized_headline = ctx.raw_headline
    ctx.normalized_body = ctx.raw_news_body
    ctx.normalized_source = "prothomalo.com"
    if top is not None:
        ctx.top_article = top
        ctx.ranked_articles = [top]
        ctx.extracted_articles = [top]
    ctx.search_attempted = 4
    ctx.search_success = 3
    ctx.search_success_empty = 1
    ctx.search_adequate = search_adequate
    return ctx


async def run_analysis(
    ctx: PipelineContext,
    *,
    ner: FakeNER | None = None,
    embedder: FakeEmbedder | None = None,
    nli=None,
) -> PipelineContext:
    """S08 -> S09 -> S11 (with the local content comparator) over deterministic fakes."""
    embedder = embedder or FakeEmbedder()
    ner = ner or FakeNER()
    nli = nli or neutral_nli()
    ctx = await SimilarityAnalyzerStage(embedder, ner).execute(ctx)
    ctx = await ContradictionDetectorStage(nli).execute(ctx)
    ctx = await ClassifierStage(ContentComparator(embedder, nli, ner, nli_validated=False)).execute(ctx)
    return ctx
