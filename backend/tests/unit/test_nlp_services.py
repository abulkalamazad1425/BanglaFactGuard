"""NER / NLI audit behaviour (no real checkpoints are loaded).

What this proves: the services refuse to present a model that fails their
wiring audit as if it were working, and report "unavailable" instead of
"no entities"/"entailment". What it does NOT prove: anything about the
accuracy of the real BanglaBERT NER or mDeBERTa checkpoints on Bangla.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.features.nlp.ner_service import NERService, _base_type
from app.features.nlp.nli_service import NLIService


@pytest.fixture(autouse=True)
def _reset():
    saved = (NERService._pipeline, NERService._loaded, NERService._labels_ok, NERService._smoke_ok,
             NLIService._pipeline, NLIService._loaded, NLIService._labels_ok)
    yield
    (NERService._pipeline, NERService._loaded, NERService._labels_ok, NERService._smoke_ok,
     NLIService._pipeline, NLIService._loaded, NLIService._labels_ok) = saved


def _fake_ner_pipe(id2label, entities):
    pipe = lambda text: entities  # noqa: E731
    pipe.model = SimpleNamespace(config=SimpleNamespace(id2label=id2label))
    return pipe


BIO = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-ORG", 4: "I-ORG", 5: "B-LOC", 6: "I-LOC"}


def test_label_mapping_strips_bio_and_rejects_generic_labels():
    assert _base_type("B-PER") == "PER" and _base_type("I-LOC") == "LOC" and _base_type("ORG") == "ORG"
    assert _base_type("B-INST") == "ORG" and _base_type("I-POL") == "ORG"
    assert _base_type("B-DATE") is None
    assert _base_type("O") is None and _base_type("LABEL_1") is None


async def test_ner_with_generic_labels_is_unavailable_not_empty():
    # the failure mode of a base (pretraining) checkpoint: LABEL_0/LABEL_1 head
    NERService._pipeline = _fake_ner_pipe({0: "LABEL_0", 1: "LABEL_1"}, [])
    NERService._loaded = True
    svc = NERService()
    await svc._run_audit()
    assert svc.usable is False and svc.audit["labels_map_to_per_loc_org"] is False
    res = await svc.extract_mentions("প্রধানমন্ত্রী শেখ হাসিনা ঢাকায় গিয়েছেন")
    assert res.available is False and res.mentions == []  # unavailable, NOT "zero entities"


async def test_ner_that_cannot_tag_the_smoke_sentence_is_not_usable():
    NERService._pipeline = _fake_ner_pipe(BIO, [])  # right labels, tags nothing
    NERService._loaded = True
    svc = NERService()
    await svc._run_audit()
    assert svc.usable is False and svc.audit["smoke_entities"] == []


async def test_functioning_ner_is_usable_and_normalises_surfaces():
    ents = [
        {"entity_group": "PER", "word": "▁শেখ হাসিনা", "score": 0.9},
        {"entity_group": "LOC", "word": "ঢাকায়", "score": 0.9},
        {"entity_group": "MISC", "word": "অন্য", "score": 0.9},
    ]
    NERService._pipeline = _fake_ner_pipe(BIO, ents)
    NERService._loaded = True
    svc = NERService()
    await svc._run_audit()
    assert svc.usable
    res = await svc.extract_mentions("প্রধানমন্ত্রী শেখ হাসিনা ঢাকায় গিয়েছেন")
    assert res.available
    assert [(m.text, m.type) for m in res.mentions] == [("শেখ হাসিনা", "PER"), ("ঢাকায়", "LOC")]


async def test_long_text_is_chunked_not_truncated_at_1000_chars():
    seen: list[str] = []

    def pipe(text):
        seen.append(text)
        return [{"entity_group": "PER", "word": "ক খ", "score": 1.0}]

    pipe.model = SimpleNamespace(config=SimpleNamespace(id2label=BIO))
    NERService._pipeline, NERService._loaded = pipe, True
    NERService._labels_ok = NERService._smoke_ok = True
    long_text = " ".join(f"বাক্য নম্বর {i} এখানে আছে।" for i in range(200))
    assert len(long_text) > 3000
    await NERService().extract_mentions(long_text)
    assert len(seen) > 1 and "199" in seen[-1]  # the tail was tagged too


def test_nli_requires_exact_entailment_neutral_contradiction_labels():
    ok = SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(
        id2label={0: "entailment", 1: "neutral", 2: "contradiction"})))
    NLIService._pipeline = ok
    NLIService()._audit_labels()
    assert NLIService._labels_ok and NLIService().audit["label_order"] == ["entailment", "neutral", "contradiction"]
    assert NLIService().audit["bangla_validated"] is False

    NLIService._pipeline = SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(
        id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})))
    NLIService()._audit_labels()
    assert NLIService._labels_ok is False


async def test_nli_with_unrecognised_labels_returns_none():
    NLIService._pipeline, NLIService._loaded, NLIService._labels_ok = object(), True, False
    assert await NLIService().predict("premise", "hypothesis") is None


def test_nli_output_is_mapped_by_label_name_not_position():
    out = [{"label": "contradiction", "score": 0.7}, {"label": "entailment", "score": 0.1}, {"label": "neutral", "score": 0.2}]
    parsed = NLIService._parse_output(out)
    assert (parsed.entailment, parsed.neutral, parsed.contradiction) == (0.1, 0.2, 0.7)
