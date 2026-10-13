from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.features.verification.analysis.decisions import decide_date
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import DateAnalysis

logger = structlog.get_logger(__name__)


class DateVerificationStage:

    stage_id = PipelineStageID.S11_DATE_VERIFICATION

    async def execute(self, context: PipelineContext) -> PipelineContext:
        confirmed = context.source_confirmed
        article = context.top_article if confirmed else None
        actual = article.published_date if article else None
        context.date_status = decide_date(context.published_date, actual, source_confirmed=confirmed)
        if confirmed:
            context.analysis.date = DateAnalysis(
                claimed_date=context.published_date,
                article_date=actual,
                article_published_at=article.published_at,
                provenance=article.published_date_source,
                tz_assumed=article.published_tz_assumed,
            )
        logger.info(
            "s11_date_verification",
            date_status=context.date_status.value if context.date_status else None,
            claimed=str(context.published_date) if context.published_date else None,
            article=str(actual) if actual else None,
        )
        return context
