from unittest.mock import MagicMock

from app.core.constants import PipelineStageID
from app.features.verification.analysis.headline_comparison import HeadlineComparator
from app.features.verification.pipeline.factory import build_verification_stages


def test_stages_run_in_the_documented_order_with_the_given_services():
    services = {name: MagicMock() for name in (
        "submission_repo", "result_repo", "article_repo", "source_repo", "cache_service",
        "embedding_service", "ner_service", "nli_service", "http_client",
    )}
    stages = build_verification_stages(**services)
    assert [s.stage_id for s in stages] == list(PipelineStageID)
    comparator = stages[8]._comparator
    assert isinstance(comparator, HeadlineComparator)
    assert (comparator.nli, comparator.embedder, comparator.ner) == (
        services["nli_service"], services["embedding_service"], services["ner_service"],
    )
    assert stages[-1].session is services["submission_repo"].session
