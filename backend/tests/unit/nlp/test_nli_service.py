"""NLI wrapper: output is mapped by label NAME, and a checkpoint without
entailment/neutral/contradiction labels is refused (None), never guessed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.features.nlp import nli_service as module
from app.features.nlp.nli_service import NLIService

GOOD = {0: "entailment", 1: "neutral", 2: "contradiction"}
OUTPUT = [{"label": "contradiction", "score": 0.7}, {"label": "ENTAILMENT", "score": 0.1}, {"label": "neutral", "score": 0.2}]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    for attr, value in (("_pipeline", None), ("_loaded", False), ("_labels_ok", False), ("_audit", {})):
        monkeypatch.setattr(NLIService, attr, value)


def install(monkeypatch, id2label, *, output=OUTPUT, error=None):
    def pipe(inputs):
        pipe.inputs.append(inputs)
        if error:
            raise error
        return output

    pipe.inputs = []
    pipe.model = SimpleNamespace(config=SimpleNamespace(id2label=id2label))
    monkeypatch.setattr(module, "hf_pipeline", lambda *a, **k: pipe)
    return pipe


async def test_scores_are_mapped_by_label_name_and_inputs_truncated(monkeypatch):
    pipe = install(monkeypatch, GOOD)
    svc = NLIService()
    assert await svc.predict("p", "h") is None  # not loaded yet
    await svc.load()
    await svc.load()
    assert svc.audit["label_order"] == ["entailment", "neutral", "contradiction"] and svc.audit["bangla_validated"] is False
    scores = await svc.predict("প" * 3000, "হ" * 1000)
    assert (scores.entailment, scores.neutral, scores.contradiction) == (0.1, 0.2, 0.7)
    assert len(pipe.inputs[0]["text"]) <= 1200 and len(pipe.inputs[0]["text_pair"]) <= 300


async def test_unrecognised_labels_or_failures_give_no_scores(monkeypatch):
    install(monkeypatch, {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})
    await NLIService().load()
    assert NLIService._labels_ok is False and await NLIService().predict("p", "h") is None

    monkeypatch.setattr(NLIService, "_loaded", False)
    install(monkeypatch, GOOD, error=RuntimeError("inference failed"))
    await NLIService().load()
    assert await NLIService().predict("p", "h") is None
    assert NLIService._parse_output([]) is None and NLIService._parse_output([{"score": 1}]) is None


async def test_a_load_failure_is_raised(monkeypatch):
    def broken(*a, **k):
        raise OSError("download failed")

    monkeypatch.setattr(module, "hf_pipeline", broken)
    with pytest.raises(OSError):
        await NLIService().load()
    assert NLIService._loaded is False
