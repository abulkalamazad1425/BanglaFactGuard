"""Photo-card stage list: the text pipeline with photo-card cache identity.

Content checking is NOT special-cased here. A photo-card headline is compared
by the same `ContentComparator` (inside the shared S11 classifier) as a
headline-only text claim; only result identity differs.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.constants import VERIFICATION_PIPELINE_VERSION, ClaimScope, PipelineStageID
from app.features.verification.analysis.content_check import METHOD
from app.features.verification.pipeline.factory import build_verification_stages
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.shared.utils.hashing import compute_claim_hash


def compute_photocard_hash(headline: str, source: str, *, published_date=None) -> str:
    """Never reuse results computed under another content method or model."""
    settings = get_settings()
    models = f"{settings.ml.embedding_model_name}:{settings.ml.nli_model_name}:{settings.ml.ner_model_name}"
    return compute_claim_hash(
        headline, source, ClaimScope.HEADLINE_ONLY, published_date=published_date,
        version=f"{VERIFICATION_PIPELINE_VERSION}:{METHOD}:{models}:{settings.classification.nli_bangla_validated}",
    )


class PhotocardNormalizerStage(InputNormalizerStage):
    async def execute(self, context):
        if context.claim_scope != ClaimScope.HEADLINE_ONLY or context.raw_news_body:
            raise ValueError("A photo card is verified on its headline only")
        context = await super().execute(context)
        context.content_hash = compute_photocard_hash(
            context.normalized_headline, context.normalized_source,
            published_date=context.published_date,
        )
        return context


def build_photocard_stages(**kwargs):
    """The shared stages, with the photo-card normalizer for result identity.

    Dispatch is explicit from PhotoCardService, never inferred from
    HEADLINE_ONLY (which also represents text submissions without a body).
    """
    return [
        PhotocardNormalizerStage(source_repo=kwargs["source_repo"])
        if stage.stage_id == PipelineStageID.S01_NORMALIZER
        else stage
        for stage in build_verification_stages(**kwargs)
    ]
