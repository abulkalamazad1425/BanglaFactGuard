"""Deterministic stand-ins for the ML services, used by stage/orchestration tests.

These fakes make decision logic testable; they say NOTHING about the accuracy
of LaBSE, the NER checkpoint or the NLI model. The "embedding" is a hashed
bag-of-stems vector (identical text -> 1.0, unrelated text -> ~0). The NLI
fake returns uninformative scores unless a pair is explicitly scripted.
"""

from __future__ import annotations

import zlib
from datetime import date
from types import SimpleNamespace

import numpy as np

from app.core.constants import ClaimScope, SearchProvider
from app.features.articles.schemas import RankedArticleSchema
from app.features.nlp.ner_service import NERResult
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.headline_comparison import HeadlineComparator
from app.features.verification.analysis.text import content_tokens, light_stem
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.features.verification.pipeline.stages.s08_source_correspondence import (
    SourceCorrespondenceStage,
)
from app.features.verification.pipeline.stages.s09_headline_alteration import (
    HeadlineAlterationStage,
)
from app.features.verification.pipeline.stages.s10_body_similarity import BodySimilarityStage
from app.features.verification.pipeline.stages.s11_date_verification import DateVerificationStage
from app.features.verification.pipeline.stages.s12_result_assembly import ResultAssemblyStage
from app.features.verification.schemas import NLIScoresSchema

DIM = 512
UNINFORMATIVE = NLIScoresSchema(entailment=0.30, contradiction=0.10, neutral=0.60)
ENTAILS = NLIScoresSchema(entailment=0.97, contradiction=0.01, neutral=0.02)
CONTRADICTS = NLIScoresSchema(entailment=0.01, contradiction=0.95, neutral=0.04)


class FakeEmbedder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
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
        if self.fail:
            raise RuntimeError("embedding model down")
        return [self._vec(t) for t in texts]

    async def compute_similarity(self, a: str, b: str) -> float:
        self.similarity_calls.append((a, b))
        if self.fail:
            raise RuntimeError("embedding model down")
        return max(0.0, min(1.0, float(np.dot(self._vec(a), self._vec(b)))))


class FakeNLI:
    """`scripted[(premise, hypothesis)]` wins; identical texts entail;
    everything else is uninformative. `available=False` -> None."""

    def __init__(self, scripted: dict | None = None, *, default: NLIScoresSchema = UNINFORMATIVE,
                 available: bool = True) -> None:
        self.scripted = scripted or {}
        self.default = default
        self.available = available
        self.calls: list[tuple[str, str]] = []

    async def predict(self, premise: str, hypothesis: str):
        self.calls.append((premise, hypothesis))
        if not self.available:
            return None
        if (premise, hypothesis) in self.scripted:
            return self.scripted[(premise, hypothesis)]
        if premise.strip() == hypothesis.strip():
            return ENTAILS
        return self.default


class FakeNER:
    """Detects any of `known` whose text occurs in the input."""

    def __init__(self, known: list[EntityMention] | None = None, *, available: bool = True) -> None:
        self.known = known or []
        self.available = available

    async def extract_mentions(self, text: str) -> NERResult:
        if not self.available:
            return NERResult(False, error="down")
        return NERResult(True, [m for m in self.known if m.text in text])


def article(
    title: str | None,
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
    articles: list[RankedArticleSchema] | None = None,
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
    ranked = articles if articles is not None else ([top] if top is not None else [])
    if ranked:
        ctx.top_article = ranked[0]
        ctx.ranked_articles = list(ranked)
        ctx.extracted_articles = list(ranked)
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
    nli: FakeNLI | None = None,
) -> PipelineContext:
    """S08 -> S12 (everything after retrieval except persistence) over fakes."""
    embedder = embedder or FakeEmbedder()
    nli = nli or FakeNLI()
    ner = ner or FakeNER()
    ctx = await SourceCorrespondenceStage(embedder).execute(ctx)
    ctx = await HeadlineAlterationStage(HeadlineComparator(nli, embedder, ner)).execute(ctx)
    ctx = await BodySimilarityStage(embedder).execute(ctx)
    ctx = await DateVerificationStage().execute(ctx)
    ctx = await ResultAssemblyStage().execute(ctx)
    return ctx


def source_record(canonical: str = "prothomalo.com", *, active: bool = True, **fields):
    """A verified_sources row as the pipeline reads it."""
    values = dict(
        id=None, canonical_name=canonical, display_name=fields.pop("display_name", canonical),
        display_name_en=None, base_url=f"https://www.{canonical}", aliases=[], is_active=active,
        body_selectors=[], title_selectors=[], date_selectors=[], internal_search_url=None,
        article_url_patterns=[],
    )
    values.update(fields)
    return SimpleNamespace(**values)


class FakeSourceRepo:
    """In-memory SourceRepository: canonical names, then aliases of active sources."""

    def __init__(self, *records) -> None:
        self.records = list(records)

    async def get_by_canonical_name(self, name: str):
        return next((r for r in self.records if r.canonical_name == name.lower().strip()), None)

    async def resolve_source(self, raw: str):
        found = await self.get_by_canonical_name(raw)
        return found or next((r for r in self.records if r.is_active and raw.strip() in (r.aliases or [])), None)

    async def list_active(self, *, limit: int = 50, **_):
        return [r for r in self.records if r.is_active][:limit]
