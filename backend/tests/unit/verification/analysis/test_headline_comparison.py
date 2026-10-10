"""Headline Alteration: claim headline vs source title ONLY. MATCHED always
needs an exact match, the same words, or positive semantic evidence."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.constants import ContentStatus, HeadlineCheckStatus
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.headline_comparison import (
    HeadlineComparator,
    exact_match_key,
    is_exact_match,
)
from app.features.verification.schemas import NLIScoresSchema
from tests.helpers.pipeline import CONTRADICTS, ENTAILS, FakeEmbedder, FakeNER, FakeNLI

RONALDO_CLAIM = "ফার্নান্দেজই পর্তুগালের ‘সবচেয়ে বড় প্রতীক’, বললেন রোনালদো"
RONALDO_TITLE = "রোনালদো বললেন, পর্তুগালের হয়ে শিরোপা ক্লাবে জেতা সব ট্রফির চেয়ে বড়"
PARAPHRASE = ("বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল", "নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক")


class FixedCosineEmbedder(FakeEmbedder):
    """Every pair has the same cosine - isolates the NLI/rule logic."""

    def __init__(self, cosine: float) -> None:
        super().__init__()
        self.cosine = cosine

    async def encode_batch(self, texts):
        self.batch_calls.append(list(texts))
        return [np.array([1.0, 0.0]), np.array([self.cosine, np.sqrt(max(0.0, 1 - self.cosine ** 2))])]


class CountingNER(FakeNER):
    calls = 0

    async def extract_mentions(self, text: str):
        self.calls += 1
        return await super().extract_mentions(text)


def comparator(nli=None, embedder=None, ner=None) -> HeadlineComparator:
    return HeadlineComparator(nli or FakeNLI(), embedder or FixedCosineEmbedder(0.9), ner or FakeNER())


async def test_exact_match_is_matched_without_running_any_model():
    nli, emb, ner = FakeNLI(), FixedCosineEmbedder(0.1), CountingNER()
    r = await comparator(nli, emb, ner).compare("সড়ক দুর্ঘটনায় ৫ জন নিহত", " সড়ক  দুর্ঘটনায় ৫ জন নিহত। ")
    assert (r.verdict, r.status, r.exact_match, r.basis) == (
        ContentStatus.MATCHED, HeadlineCheckStatus.COMPLETED, True, "exact",
    )
    assert nli.calls == [] and emb.batch_calls == [] and ner.calls == 0


def test_exact_match_normalisation_never_erases_meaning():
    assert exact_match_key("  ঢাকায়​  বৃষ্টি।") == "ঢাকায় বৃষ্টি"
    assert exact_match_key("‘ঢাকায়’ বৃষ্টি, তবে কম?") == "‘ঢাকায়’ বৃষ্টি, তবে কম"
    for claim, title in [
        ("সড়ক দুর্ঘটনায় ৫ জন নিহত", "সড়ক দুর্ঘটনায় ৬ জন নিহত"),
        ("সরকার দাম বাড়িয়েছে", "সরকার দাম বাড়ায়নি"),
        ("‘সবচেয়ে বড় প্রতীক’, বললেন রোনালদো", "সবচেয়ে বড় প্রতীক, বললেন রোনালদো"),
        ("মেসি, রোনালদো", "মেসি রোনালদো"),
        ("সাকিব অবসর নিলেন", "তামিম অবসর নিলেন"),
    ]:
        assert not is_exact_match(claim, title)


async def test_matched_needs_same_words_or_semantic_equivalence():
    same_words = await comparator().compare(
        "‘ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক’, বললেন রোনালদো",
        "ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক, বললেন রোনালদো",
    )
    assert (same_words.verdict, same_words.basis) == (ContentStatus.MATCHED, "same_words")

    claim, title = PARAPHRASE
    nli = FakeNLI({(title, claim): ENTAILS})
    semantic = await comparator(nli).compare(claim, title)
    assert (semantic.verdict, semantic.basis) == (ContentStatus.MATCHED, "semantic_equivalence")
    assert (title, claim) in nli.calls and (claim, title) in nli.calls  # both directions
    # equivalence also needs the embedding to agree
    low_cosine = await comparator(nli, FixedCosineEmbedder(0.3)).compare(claim, title)
    assert low_cosine.verdict != ContentStatus.MATCHED


async def test_no_conflict_found_is_not_an_automatic_match():
    claim, title = "পদ্মা সেতু দিয়ে যান চলাচল শুরু", "উদ্বোধনের পরদিন পদ্মা সেতু দিয়ে যান চলাচল শুরু"
    r = await comparator(FakeNLI()).compare(claim, title)
    assert (r.verdict, r.status, r.differences) == (None, HeadlineCheckStatus.UNDETERMINED, [])


@pytest.mark.parametrize("nli", [FakeNLI(), FakeNLI({(RONALDO_TITLE, RONALDO_CLAIM): CONTRADICTS})])
async def test_same_speaker_different_main_statement_is_altered(nli):
    r = await comparator(nli).compare(RONALDO_CLAIM, RONALDO_TITLE)
    assert r.verdict == ContentStatus.ALTERED and r.basis == "semantic_divergence"
    assert r.differences[0].kind == "main_point" and "প্রতীক" in r.reason
    # medium entailment with a very high embedding similarity is still never MATCHED
    medium = FakeNLI({(RONALDO_TITLE, RONALDO_CLAIM): NLIScoresSchema(entailment=0.6, contradiction=0.1, neutral=0.3)})
    assert (await comparator(medium, FixedCosineEmbedder(0.97)).compare(RONALDO_CLAIM, RONALDO_TITLE)).verdict is None


async def test_a_material_difference_is_altered_even_when_the_model_entails():
    claim, title = "সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত"
    nli = FakeNLI({(title, claim): ENTAILS})
    r = await comparator(nli).compare(claim, title)
    assert (r.verdict, r.basis) == (ContentStatus.ALTERED, "material_difference")
    assert r.semantic.available and nli.calls  # the semantic assessment still ran
    down = await comparator(FakeNLI(available=False)).compare(claim, title)
    assert down.verdict == ContentStatus.ALTERED  # a concrete difference needs no model


async def test_entities_are_compared_only_when_ner_is_usable():
    ner = FakeNER([EntityMention("সাকিব আল হাসান", "PER"), EntityMention("তামিম ইকবাল", "PER")])
    claim, title = "সাকিব আল হাসান অবসরের ঘোষণা দিলেন", "তামিম ইকবাল অবসরের ঘোষণা দিলেন"
    r = await comparator(FakeNLI(), ner=ner).compare(claim, title)
    assert r.verdict == ContentStatus.ALTERED and r.ner_available
    assert next(d for d in r.differences if d.kind == "entity").claim_text == "সাকিব আল হাসান"

    class BrokenNER:
        async def extract_mentions(self, text):
            raise RuntimeError("ner down")

    for broken in (FakeNER(available=False), BrokenNER()):
        assert (await comparator(FakeNLI(), ner=broken).compare(claim, title)).ner_available is False


async def test_missing_inputs_or_models_give_no_verdict_instead_of_a_guess():
    no_title = await comparator().compare("ঢাকায় ভারী বৃষ্টি", None)
    assert (no_title.verdict, no_title.status) == (None, HeadlineCheckStatus.SOURCE_TITLE_MISSING)
    assert "no headline" in (await comparator().compare("", "শিরোনাম")).reason

    claim, title = "দেশে স্বর্ণের দাম আবার বাড়ল", "আবারও বাড়ল স্বর্ণের দাম"

    class RaisingNLI:
        async def predict(self, premise, hypothesis):
            raise RuntimeError("nli crashed")

    for nli in (FakeNLI(available=False), RaisingNLI()):
        r = await comparator(nli).compare(claim, title)
        assert (r.verdict, r.status) == (None, HeadlineCheckStatus.MODEL_UNAVAILABLE)
    too_long = await comparator().compare(claim + " " + "শব্দ " * 80, title)
    assert too_long.status == HeadlineCheckStatus.MODEL_UNAVAILABLE and "too long" in too_long.reason
    no_nli = await HeadlineComparator(None, FakeEmbedder()).compare(claim, title)
    assert no_nli.status == HeadlineCheckStatus.MODEL_UNAVAILABLE

    entailed = FakeNLI({(title, claim): ENTAILS})
    no_embedding = await comparator(entailed, FakeEmbedder(fail=True)).compare(claim, title)
    assert no_embedding.verdict is None and no_embedding.semantic.embedding_cosine is None
