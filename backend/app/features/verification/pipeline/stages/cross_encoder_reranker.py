import asyncio
import threading
from typing import List

import structlog
from sentence_transformers import CrossEncoder

from app.features.articles.schemas import RankedArticleSchema

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:

    MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    # The ranker stage is rebuilt for every verification, and loading a
    # transformer each time cost seconds of wall clock on the API's event
    # loop. The weights are read-only, so share one instance process-wide.
    _model: CrossEncoder | None = None
    _load_lock = threading.Lock()
    _load_failed = False

    @classmethod
    def _get_model(cls) -> CrossEncoder | None:
        if cls._model is not None or cls._load_failed:
            return cls._model
        with cls._load_lock:
            if cls._model is None and not cls._load_failed:
                try:
                    cls._model = CrossEncoder(cls.MODEL_NAME)
                    logger.info("cross_encoder_loaded", model=cls.MODEL_NAME)
                except Exception as exc:
                    cls._load_failed = True
                    logger.error("cross_encoder_load_failed", error=str(exc))
        return cls._model

    @property
    def model(self) -> CrossEncoder | None:
        return self._get_model()

    async def rerank(
        self, claim_headline: str, articles: List[RankedArticleSchema], top_k: int = 3
    ) -> List[RankedArticleSchema]:
        """Re-order candidates with a cross-encoder.

        Awaitable because the forward pass is CPU-bound: run inline it froze
        the whole API for the duration, so a queued verification could delay
        unrelated requests by seconds. It runs on a worker thread instead.
        """
        if not articles or len(articles) <= 3:
            return articles

        model = self._get_model()
        if model is None:
            return articles

        pairs = []
        for article in articles:
            title = article.title or ""
            body_preview = (article.body or "")[:500]
            article_text = f"{title} {body_preview}".strip()
            pairs.append((claim_headline, article_text))

        try:
            scores = await asyncio.to_thread(model.predict, pairs)

            scored_articles = list(zip(scores, articles))
            scored_articles.sort(key=lambda x: x[0], reverse=True)

            return [article for score, article in scored_articles[:top_k]]
        except Exception as exc:
            logger.warning("cross_encoder_predict_failed", error=str(exc))
            return articles
