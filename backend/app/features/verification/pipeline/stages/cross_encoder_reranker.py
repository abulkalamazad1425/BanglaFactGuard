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

    async def scores(self, claim_headline: str, articles: List[RankedArticleSchema]) -> List[float] | None:
        """Cross-encoder relevance of each article to the claim, or None when
        the model is unavailable or fails."""
        if not articles:
            return []
        model = self._get_model()
        if model is None:
            return None
        pairs = [
            (claim_headline, f"{a.title or ''} {(a.body or '')[:500]}".strip())
            for a in articles
        ]
        try:
            return [float(s) for s in await asyncio.to_thread(model.predict, pairs)]
        except Exception as exc:
            logger.warning("cross_encoder_predict_failed", error=str(exc))
            return None
