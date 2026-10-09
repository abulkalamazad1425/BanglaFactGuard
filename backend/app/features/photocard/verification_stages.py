"""The shared verification stages, wired for a photo card.

A photo card runs the very same S01-S13 pipeline as a typed claim; only the
normaliser differs, so that the result identity (content hash) of a card is
computed under the photo-card rules: headline only, never a body.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.constants import VERIFICATION_PIPELINE_VERSION, ClaimScope, PipelineStageID
from app.features.nlp.model_identity import embedding_identity_tag
from app.features.verification.analysis.headline_comparison import METHOD
from app.features.verification.pipeline.factory import build_verification_stages
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.source_policy import verified_identity_key
from app.shared.utils.hashing import compute_claim_hash


def compute_photocard_hash(headline: str, source: str, *, published_date=None) -> str:
    """Never reuse a result computed under another pipeline version, headline
    comparison method or model set."""
    settings = get_settings()
    embedding = embedding_identity_tag(settings.ml.embedding_model_name)
    models = f"{embedding}:{settings.ml.nli_model_name}:{settings.ml.ner_model_name}"
    return compute_claim_hash(
        headline, source, ClaimScope.HEADLINE_ONLY, published_date=published_date,
        version=f"{VERIFICATION_PIPELINE_VERSION}:{METHOD}:{models}",
    )


class PhotocardNormalizerStage(InputNormalizerStage):
    async def execute(self, context):
        if context.claim_scope != ClaimScope.HEADLINE_ONLY or context.raw_news_body:
            raise ValueError("A photo card is verified on its headline only")
        context = await super().execute(context)
        identity_source = (
            verified_identity_key(context.verified_scope)
            if context.is_verified_sources_mode
            else context.normalized_source
        )
        context.content_hash = compute_photocard_hash(
            context.normalized_headline, identity_source,
            published_date=context.published_date,
        )
        return context


def build_photocard_stages(**kwargs):
    """The shared stages with the photo-card normaliser. Dispatch is explicit
    from PhotoCardService, never inferred from HEADLINE_ONLY (which also
    describes text claims submitted without a body)."""
    return [
        PhotocardNormalizerStage(source_repo=kwargs["source_repo"])
        if stage.stage_id == PipelineStageID.S01_NORMALIZER
        else stage
        for stage in build_verification_stages(**kwargs)
    ]
