"""Headline Alteration comparator: claim headline vs source title ONLY.

Fakes keep these deterministic. One optional test runs the real local
models (set BFG_REAL_MODEL_TESTS=1; needs the cached HuggingFace models).
"""

from __future__ import annotations

import os

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
from tests.unit.pipeline_helpers import CONTRADICTS, ENTAILS, FakeEmbedder, FakeNER, FakeNLI

RONALDO_CLAIM = "ফার্নান্দেজই পর্তুগালের ‘সবচেয়ে বড় প্রতীক’, বললেন রোনালদো"
RONALDO_TITLE = "রোনালদো বললেন, পর্তুগালের হয়ে শিরোপা ক্লাবে জেতা সব ট্রফির চেয়ে বড়"


class FixedCosineEmbedder(FakeEmbedder):
    """Every pair has the same cosine - isolates the NLI/rule logic."""

    def __init__(self, cosine: float) -> None:
        super().__init__()
        self.cosine = cosine

    async def encode_batch(self, texts):
        self.batch_calls.append(list(texts))
        a = np.array([1.0, 0.0])
        b = np.array([self.cosine, np.sqrt(max(0.0, 1 - self.cosine ** 2))])
        return [a, b]


class CountingNER(FakeNER):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.calls = 0

    async def extract_mentions(self, text: str):
        self.calls += 1
        return await super().extract_mentions(text)


def comparator(nli=None, embedder=None, ner=None) -> HeadlineComparator:
    return HeadlineComparator(nli or FakeNLI(), embedder or FixedCosineEmbedder(0.9), ner or FakeNER())


# ── exact match ──────────────────────────────────────────────────────────

async def test_exact_match_is_matched_and_skips_every_alteration_analysis():
    nli, emb, ner = FakeNLI(), FixedCosineEmbedder(0.1), CountingNER()
    result = await comparator(nli, emb, ner).compare("সড়ক দুর্ঘটনায় ৫ জন নিহত", " সড়ক  দুর্ঘটনায় ৫ জন নিহত। ")
    assert result.verdict == ContentStatus.MATCHED
    assert result.status == HeadlineCheckStatus.COMPLETED
    assert result.exact_match is True and result.basis == "exact"
    assert nli.calls == [] and emb.batch_calls == [] and ner.calls == 0


@pytest.mark.parametrize("claim,title", [
    ("সড়ক দুর্ঘটনায় ৫ জন নিহত", "সড়ক দুর্ঘটনায় ৬ জন নিহত"),          # number
    ("সরকার দাম বাড়িয়েছে", "সরকার দাম বাড়ায়নি"),                    # negation
    ("‘সবচেয়ে বড় প্রতীক’, বললেন রোনালদো", "সবচেয়ে বড় প্রতীক, বললেন রোনালদো"),  # quotes
    ("মেসি, রোনালদো", "মেসি রোনালদো"),                                # internal punctuation
    ("সাকিব অবসর নিলেন", "তামিম অবসর নিলেন"),                        # name
])
def test_exact_match_normalisation_never_erases_meaningful_characters(claim, title):
    assert not is_exact_match(claim, title)


def test_exact_match_normalisation_is_limited_to_documented_rules():
    assert exact_match_key("  ঢাকায়​  বৃষ্টি।") == "ঢাকায় বৃষ্টি"
    assert exact_match_key("ঢাকায় বৃষ্টি?") == "ঢাকায় বৃষ্টি"
    assert exact_match_key("‘ঢাকায়’ বৃষ্টি, তবে কম") == "‘ঢাকায়’ বৃষ্টি, তবে কম"


# ── non-exact: positive evidence required ────────────────────────────────

async def test_genuine_paraphrase_is_matched_on_semantic_evidence():
    claim, title = "বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল", "নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক"
    nli = FakeNLI({(title, claim): ENTAILS})
    result = await comparator(nli).compare(claim, title)
    assert result.verdict == ContentStatus.MATCHED
    assert result.basis == "semantic_equivalence" and not result.exact_match
    assert (title, claim) in nli.calls


async def test_ronaldo_fernandes_regression_pair_is_altered():
    """Same speaker and country, different main statement. With an
    uninformative semantic model the headline still cannot be MATCHED: the
    title does not support what the headline says about Fernandes."""
    result = await comparator(FakeNLI()).compare(RONALDO_CLAIM, RONALDO_TITLE)
    assert result.verdict == ContentStatus.ALTERED
    assert result.status == HeadlineCheckStatus.COMPLETED
    assert any(d.kind == "main_point" for d in result.differences)
    assert "প্রতীক" in result.reason


async def test_ronaldo_pair_is_altered_when_the_model_reports_contradiction():
    nli = FakeNLI({(RONALDO_TITLE, RONALDO_CLAIM): CONTRADICTS})
    result = await comparator(nli).compare(RONALDO_CLAIM, RONALDO_TITLE)
    assert result.verdict == ContentStatus.ALTERED


async def test_ronaldo_pair_is_never_matched_by_high_embedding_similarity():
    medium = NLIScoresSchema(entailment=0.6, contradiction=0.1, neutral=0.3)
    nli = FakeNLI({(RONALDO_TITLE, RONALDO_CLAIM): medium})
    result = await comparator(nli, FixedCosineEmbedder(0.97)).compare(RONALDO_CLAIM, RONALDO_TITLE)
    assert result.verdict != ContentStatus.MATCHED


async def test_shared_entities_and_topic_with_a_different_main_statement_is_not_matched():
    claim = "মেসি বললেন, আর্জেন্টিনার হয়ে আর খেলবেন না"
    title = "মেসি বললেন, আর্জেন্টিনার হয়ে বিশ্বকাপ জেতা তাঁর জীবনের সেরা মুহূর্ত"
    ner = FakeNER([EntityMention("মেসি", "PER"), EntityMention("আর্জেন্টিনার", "LOC")])
    result = await comparator(FakeNLI(), FixedCosineEmbedder(0.9), ner).compare(claim, title)
    assert result.verdict == ContentStatus.ALTERED


async def test_finding_no_conflict_is_not_an_automatic_match():
    """Every headline word is in the title and no rule fires, but the model
    does not establish equivalence: no verdict, never a silent MATCHED."""
    claim, title = "পদ্মা সেতু দিয়ে যান চলাচল শুরু", "উদ্বোধনের পরদিন পদ্মা সেতু দিয়ে যান চলাচল শুরু"
    result = await comparator(FakeNLI()).compare(claim, title)
    assert result.verdict is None
    assert result.status == HeadlineCheckStatus.UNDETERMINED
    assert result.differences == []
    matched = await comparator(FakeNLI({(title, claim): ENTAILS})).compare(claim, title)
    assert matched.verdict == ContentStatus.MATCHED


async def test_punctuation_only_difference_is_matched():
    result = await comparator(FakeNLI()).compare(
        "‘ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক’, বললেন রোনালদো",
        "ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক, বললেন রোনালদো",
    )
    assert result.verdict == ContentStatus.MATCHED and result.basis == "same_words"


# ── material differences ─────────────────────────────────────────────────

@pytest.mark.parametrize("claim,title,kind", [
    ("সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত", "numbers"),
    ("সড়ক দুর্ঘটনায় ৫ জন নিহত", "সড়ক দুর্ঘটনায় নিহত বেড়েছে", "numbers"),
    ("সরকার জ্বালানি তেলের দাম বাড়ায়নি", "সরকার জ্বালানি তেলের দাম বাড়িয়েছে", "negation"),
    ("পুলিশকে মারধর করল শিক্ষার্থীরা", "শিক্ষার্থীদের মারধর করল পুলিশ", "subject_object"),
    ("নির্বাচন হবে ডিসেম্বরে", "নির্বাচন হবে ফেব্রুয়ারিতে", "date"),
    ("মন্ত্রী দুর্নীতি করেছেন", "মন্ত্রী দুর্নীতি করেছেন বলে অভিযোগ বিরোধী দলের", "attribution"),
])
async def test_material_difference_is_altered_with_quoted_evidence(claim, title, kind):
    result = await comparator(FakeNLI({(title, claim): ENTAILS})).compare(claim, title)
    assert result.verdict == ContentStatus.ALTERED
    assert result.basis == "material_difference"
    assert kind in {d.kind for d in result.differences}
    assert all(d.claim_text and d.source_text for d in result.differences)


async def test_entity_substitution_is_altered():
    ner = FakeNER([EntityMention("সাকিব আল হাসান", "PER"), EntityMention("তামিম ইকবাল", "PER")])
    result = await comparator(FakeNLI(), ner=ner).compare("সাকিব আল হাসান অবসরের ঘোষণা দিলেন", "তামিম ইকবাল অবসরের ঘোষণা দিলেন")
    assert result.verdict == ContentStatus.ALTERED
    diff = next(d for d in result.differences if d.kind == "entity")
    assert diff.claim_text == "সাকিব আল হাসান" and "তামিম ইকবাল" in diff.source_text


async def test_semantic_assessment_runs_on_every_non_exact_comparison_even_when_a_rule_fires():
    claim, title = "সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত"
    nli = FakeNLI({(title, claim): ENTAILS})
    result = await comparator(nli).compare(claim, title)
    assert result.semantic is not None and result.semantic.available
    assert nli.calls  # ran, and its entailment did not cancel the number change
    assert result.verdict == ContentStatus.ALTERED


# ── no verdict ───────────────────────────────────────────────────────────

async def test_missing_source_title_gives_no_verdict():
    result = await comparator().compare("ঢাকায় ভারী বৃষ্টি", None)
    assert result.verdict is None and result.status == HeadlineCheckStatus.SOURCE_TITLE_MISSING


async def test_model_failure_gives_no_verdict_instead_of_a_guess():
    claim, title = "দেশে স্বর্ণের দাম আবার বাড়ল", "আবারও বাড়ল স্বর্ণের দাম"
    result = await comparator(FakeNLI(available=False)).compare(claim, title)
    assert result.verdict is None and result.status == HeadlineCheckStatus.MODEL_UNAVAILABLE


async def test_concrete_difference_is_still_altered_when_the_model_is_down():
    result = await comparator(FakeNLI(available=False)).compare("সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত")
    assert result.verdict == ContentStatus.ALTERED


# ── optional: the deployed local models ──────────────────────────────────

@pytest.mark.skipif(os.environ.get("BFG_REAL_MODEL_TESTS") != "1", reason="set BFG_REAL_MODEL_TESTS=1 to run with local models")
async def test_ronaldo_pair_with_the_real_local_models():
    from app.features.nlp.embedding_service import EmbeddingService
    from app.features.nlp.ner_service import NERService
    from app.features.nlp.nli_service import NLIService

    class NoCache:
        async def get_raw(self, key):
            return None

    emb, nli, ner = EmbeddingService(NoCache()), NLIService(), NERService()
    await emb.load(); await nli.load(); await ner.load()
    comp = HeadlineComparator(nli, emb, ner)
    assert (await comp.compare(RONALDO_CLAIM, RONALDO_TITLE)).verdict == ContentStatus.ALTERED
    para = await comp.compare("প্রধানমন্ত্রী আজ পদ্মা সেতু উদ্বোধন করেছেন", "আজ পদ্মা সেতুর উদ্বোধন করলেন প্রধানমন্ত্রী")
    assert para.verdict == ContentStatus.MATCHED
