"""NER audit: a checkpoint that fails the label or smoke audit is reported
UNAVAILABLE, never as "no entities". No real checkpoint is loaded; nothing
here says anything about BanglaTag's accuracy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.features.nlp import ner_service as module
from app.features.nlp.ner_service import NERService, _base_type

BIO = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-ORG", 4: "I-ORG", 5: "B-LOC", 6: "I-LOC"}
SENTENCE = "প্রধানমন্ত্রী শেখ হাসিনা ঢাকায় গিয়েছেন"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    for attr, value in (("_pipeline", None), ("_loaded", False), ("_labels_ok", False), ("_smoke_ok", False), ("_audit", {})):
        monkeypatch.setattr(NERService, attr, value)


def fake_pipe(id2label, entities, *, error=None):
    def pipe(text):
        pipe.seen.append(text)
        if error:
            raise error
        return entities

    pipe.seen = []
    pipe.model = SimpleNamespace(config=SimpleNamespace(id2label=id2label))
    return pipe


def install(monkeypatch, pipe):
    monkeypatch.setattr(module, "hf_pipeline", lambda *a, **k: pipe)


def test_labels_map_bio_and_banglatag_types_and_reject_generic_ones():
    assert [_base_type(x) for x in ("B-PER", "I-LOC", "ORG", "B-INST", "I-POL")] == ["PER", "LOC", "ORG", "ORG", "ORG"]
    assert [_base_type(x) for x in ("B-DATE", "O", "LABEL_1")] == [None, None, None]


async def test_a_working_checkpoint_is_usable_and_normalises_surfaces(monkeypatch):
    install(monkeypatch, fake_pipe(BIO, [
        {"entity_group": "PER", "word": "▁শেখ হাসিনা", "score": 0.9},
        {"entity_group": "LOC", "word": "ঢাকায়", "score": 0.9},
        {"entity_group": "LOC", "word": "ঢাকায়", "score": 0.8},   # duplicate
        {"entity_group": "MISC", "word": "অন্য", "score": 0.9},   # not a kept type
        {"entity": "B-PER", "word": "##ক", "score": 0.9},         # sub-word fragment
    ]))
    svc = NERService()
    await svc.load()
    await svc.load()  # once
    assert svc.usable and svc.audit["usable"] and svc.audit["accuracy_validated"] is False
    res = await svc.extract_mentions(SENTENCE)
    assert res.available and [(m.text, m.type) for m in res.mentions] == [("শেখ হাসিনা", "PER"), ("ঢাকায়", "LOC")]
    assert (await svc.extract_mentions("ক")).mentions == []


@pytest.mark.parametrize("id2label,entities", [
    ({0: "LABEL_0", 1: "LABEL_1"}, []),   # a pretraining checkpoint: no NER head
    (BIO, []),                           # right labels, but tags nothing in the smoke sentence
])
async def test_a_checkpoint_failing_its_audit_is_unavailable_not_empty(monkeypatch, id2label, entities):
    install(monkeypatch, fake_pipe(id2label, entities))
    svc = NERService()
    await svc.load()
    assert not svc.usable
    res = await svc.extract_mentions(SENTENCE)
    assert res.available is False and res.mentions == []


async def test_long_text_is_chunked_and_inference_errors_are_unavailable(monkeypatch):
    pipe = fake_pipe(BIO, [{"entity_group": "PER", "word": "ক খ", "score": 1.0}])
    install(monkeypatch, pipe)
    svc = NERService()
    await svc.load()
    long_text = " ".join(f"বাক্য নম্বর {i} এখানে আছে।" for i in range(200))
    await svc.extract_mentions(long_text)
    assert len(pipe.seen) > 2 and "199" in pipe.seen[-1]  # the tail was tagged too, not truncated
    NERService._pipeline = fake_pipe(BIO, [], error=RuntimeError("cuda"))
    assert (await svc.extract_mentions(SENTENCE)).available is False


async def test_a_load_failure_is_raised(monkeypatch):
    def broken(*a, **k):
        raise OSError("download failed")

    monkeypatch.setattr(module, "hf_pipeline", broken)
    with pytest.raises(OSError):
        await NERService().load()
    assert not NERService().usable
