import pytest

from app.features.verification.pipeline.stages import cross_encoder_reranker as module
from app.features.verification.pipeline.stages.cross_encoder_reranker import CrossEncoderReranker
from tests.helpers.pipeline import article


@pytest.fixture(autouse=True)
def fresh_model(monkeypatch):
    monkeypatch.setattr(CrossEncoderReranker, "_model", None)
    monkeypatch.setattr(CrossEncoderReranker, "_load_failed", False)


class FakeCrossEncoder:
    loads = 0

    def __init__(self, name):
        FakeCrossEncoder.loads += 1
        self.fail = False

    def predict(self, pairs):
        if self.fail:
            raise RuntimeError("predict failed")
        return [len(text) for _, text in pairs]


async def test_scores_pair_the_claim_with_each_article_and_the_model_loads_once(monkeypatch):
    FakeCrossEncoder.loads = 0
    monkeypatch.setattr(module, "CrossEncoder", FakeCrossEncoder)
    articles = [article("ক", "খ"), article("কক", None)]
    assert await CrossEncoderReranker().scores("দাবি", articles) == [3.0, 2.0]
    assert await CrossEncoderReranker().scores("দাবি", []) == []
    assert FakeCrossEncoder.loads == 1  # shared process-wide
    CrossEncoderReranker._model.fail = True
    assert await CrossEncoderReranker().scores("দাবি", articles) is None


async def test_an_unloadable_model_is_reported_as_unavailable_and_not_retried(monkeypatch):
    attempts = []

    def broken(name):
        attempts.append(name)
        raise OSError("no weights")

    monkeypatch.setattr(module, "CrossEncoder", broken)
    assert await CrossEncoderReranker().scores("দাবি", [article("t")]) is None
    assert CrossEncoderReranker().model is None and len(attempts) == 1
