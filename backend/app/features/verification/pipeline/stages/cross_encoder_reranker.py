
from typing import List
import structlog
from sentence_transformers import CrossEncoder

from app.features.articles.schemas import RankedArticleSchema

logger = structlog.get_logger(__name__)

class CrossEncoderReranker:

    MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    def __init__(self) -> None:
        try:
            self.model = CrossEncoder(self.MODEL_NAME)
            logger.info("cross_encoder_loaded", model=self.MODEL_NAME)
        except Exception as exc:
            logger.error("cross_encoder_load_failed", error=str(exc))
            self.model = None

    def rerank(self, claim_headline: str, articles: List[RankedArticleSchema], top_k: int = 3) -> List[RankedArticleSchema]:
        if not self.model or not articles:
            return articles

        if len(articles) <= 3:
            return articles


        pairs = []
        for article in articles:
            title = article.title or ""
            body_preview = (article.body or "")[:500]
            article_text = f"{title} {body_preview}".strip()
            pairs.append((claim_headline, article_text))

        try:
            scores = self.model.predict(pairs)
            

            scored_articles = list(zip(scores, articles))
            scored_articles.sort(key=lambda x: x[0], reverse=True)
            

            return [article for score, article in scored_articles[:top_k]]
        except Exception as exc:
            logger.warning("cross_encoder_predict_failed", error=str(exc))
            return articles
