from __future__ import annotations

from enum import Enum


class SourceStatus(str, Enum):
    """Does the claimed source actually carry this story at all?

    Checked first, independently of content or date: a story the source
    never published is NOT_FOUND regardless of what the claim says, and a
    story it did publish is CONFIRMED regardless of how the claim words it.

    INCOMPLETE is distinct from NOT_FOUND: NOT_FOUND means an adequate search
    actually ran and came up empty; INCOMPLETE means the search or retrieval
    itself failed (every provider errored, every fetch failed) and no
    conclusion could be reached either way. A failed check must never be
    reported as a confident negative — see s11_classifier.py.
    """

    CONFIRMED = "CONFIRMED"
    NOT_FOUND = "NOT_FOUND"
    INCOMPLETE = "INCOMPLETE"


class ContentStatus(str, Enum):
    """How the claimed content compares to the source once CONFIRMED.

    Only meaningful when source_status is CONFIRMED — there is nothing to
    compare content against when the source never published the story (that
    case is represented as NULL/not-applicable, not INCOMPLETE). MATCHED
    covers paraphrase and reordering that preserve the same facts; ALTERED is
    reserved for material factual changes (numbers, names, outcomes) or
    outright contradiction. INCOMPLETE means the source WAS confirmed but the
    evidence needed to compare content (e.g. the article body) could not be
    retrieved or was too ambiguous to judge.
    """

    MATCHED = "MATCHED"
    ALTERED = "ALTERED"
    INCOMPLETE = "INCOMPLETE"


class DateStatus(str, Enum):
    """Does the claimed publication date match the source's actual date?

    Only meaningful when source_status is CONFIRMED. A mismatch here is
    informational, not a verdict on the content — a claim can be MISMATCHED
    on date while its content is still MATCHED (e.g. a screenshot circulated
    years after original publication). INCOMPLETE means the source's actual
    publication date could not be determined (missing or ambiguous
    datePublished) — this is not the same as MISMATCHED, and must never be
    reported as one.
    """

    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    INCOMPLETE = "INCOMPLETE"


class OverallVerdict(str, Enum):
    """The headline editorial verdict experts vote on for EVERY submission
    type (source-based, photo card, and multimodal alike) — distinct from,
    and voted on independently of, the (Source, Content, Date) structured
    vote that additionally exists for source-based/photo-card claims.

    An expert may, for example, judge Source=CONFIRMED/Content=ALTERED but
    still cast ALTERED here rather than mechanically deriving it — this is
    the expert's own editorial call, not a projection of the other fields.
    """

    FAKE = "FAKE"
    REAL = "REAL"
    MISLEADING = "MISLEADING"
    ALTERED = "ALTERED"


class ExpertVerdict(str, Enum):
    """A human expert's own single-category judgment call on a claim.

    Deliberately separate from the AI pipeline's (SourceStatus, ContentStatus,
    DateStatus) triple: expert review is a credibility-weighted consensus vote
    that predates and is independent of this task's 3-dimensional verdict
    model, and collapsing three experts' votes across three independent axes
    into one weighted consensus is a distinct, unspecified design problem.
    This enum keeps that existing voting/credibility-scoring subsystem
    working unchanged. It is never returned as "the verdict" from the
    verification pipeline itself — see VerificationResponse.
    """

    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    NOT_FOUND_IN_CLAIMED_SOURCE = "NOT_FOUND_IN_CLAIMED_SOURCE"


class ClaimStatus(str, Enum):

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchProvider(str, Enum):

    INTERNAL_SITE = "internal_site"
    NEWSDATA = "newsdata"
    GOOGLE_CUSTOM_SEARCH = "google_custom_search"
    PY_GOOGLE_NEWS = "py_google_news"

    SEARXNG = "searxng"
    GOOGLE_RSS = "google_rss"
    DDG = "ddg"
    BRAVE = "brave"


class QueryType(str, Enum):

    HEADLINE = "headline"
    KEYWORDS = "keywords"
    ENTITIES = "entities"
    DATE_BOUND = "date_bound"
    BODY_SUMMARY = "body_summary"
    SITE_RESTRICTED = "site_restricted"


class ExtractionMethod(str, Enum):

    JSON_LD = "json_ld"
    OPENGRAPH = "opengraph"
    SOURCE_SPECIFIC = "source_specific"
    TRAFILATURA = "trafilatura"
    READABILITY = "readability"
    BEAUTIFULSOUP = "beautifulsoup"


class NLILabel(str, Enum):

    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


class ManipulationType(str, Enum):

    HEADLINE_MANIPULATED = "headline_manipulated"
    BODY_ALTERED = "body_altered"
    NUMBERS_ALTERED = "numbers_altered"
    ENTITIES_REPLACED = "entities_replaced"


class LogLevel(str, Enum):

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class SubmissionType(str, Enum):

    MULTIMODAL = "MULTIMODAL"
    SOURCE_BASED = "SOURCE_BASED"
    PHOTO_CARD = "PHOTO_CARD"


class ClaimScope(str, Enum):
    """What the pipeline is allowed to use as "the claim" when comparing
    against source evidence.

    PHOTO_CARD submissions are always HEADLINE_ONLY: the business rule is
    that a photo card is verified against its extracted headline alone — no
    body/caption text is checked, and nothing is synthesised to stand in for
    one. SOURCE_BASED text claims are HEADLINE_WITH_BODY whenever the user
    supplied body text, HEADLINE_ONLY otherwise. This is part of claim
    identity: it is folded into the content hash (`hashing.compute_claim_hash`)
    so a HEADLINE_ONLY run and a HEADLINE_WITH_BODY run of the same
    headline+source never collide in the cache and silently serve each other
    a score computed over different input.
    """

    HEADLINE_ONLY = "HEADLINE_ONLY"
    HEADLINE_WITH_BODY = "HEADLINE_WITH_BODY"


class SubmissionStatus(str, Enum):
    """SUBMITTED/AI_PROCESSING/AI_PRELIMINARY/UNDER_REVIEW/EXPERT_VERIFIED in
    the SRS state-machine map to PENDING/PROCESSING/EXPERT_REVIEW/FINALIZED
    here — same lifecycle, pre-existing names kept rather than renamed across
    the whole codebase. ESCALATED is the one genuinely new terminal state:
    a claim that hit its configured review window/vote cap without reaching
    consensus, now awaiting an admin's manual resolution instead of further
    expert votes.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    EXPERT_REVIEW = "EXPERT_REVIEW"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class MultimodalPredictionLabel(str, Enum):

    FAKE = "FAKE"
    NON_FAKE = "NON_FAKE"


class CheckState(str, Enum):
    """Outcome of one alteration/consistency check — never inferred from a
    default-False flag. PASSED means the check ran to completion and found no
    concrete discrepancy; NOT_EVALUATED means it could not run (missing
    signal, failed model, absent evidence) and is NOT a pass; NOT_APPLICABLE
    means the check does not apply to this claim scope (e.g. any submitted-body
    check for a photo card)."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MetricState(str, Enum):
    """Why a score is (or is not) a number.

    COMPUTED       — a real measurement; the value may legitimately be 0.0.
    NOT_APPLICABLE — the metric has no meaning for this claim (photo-card body
                     similarity, entity coverage with no claim entities).
    EMPTY          — the claim side produced nothing to measure (keyword
                     extraction returned no applicable units).
    UNAVAILABLE    — the utility/model/evidence needed was missing or failed.
    """

    COMPUTED = "COMPUTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"


class SearchCallOutcome(str, Enum):
    """Per provider-call accounting for S04 — the only honest basis for
    deciding whether a search was adequate."""

    SUCCESS = "SUCCESS"
    SUCCESS_EMPTY = "SUCCESS_EMPTY"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CACHED = "CACHED"


class JobPhase(str, Enum):
    """Fine-grained progress inside the public PENDING/PROCESSING lifecycle."""

    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    FAILED = "FAILED"


# Bumped whenever scoring/decision logic changes in a way that makes earlier
# stored scores non-comparable. It is part of claim identity, so results
# produced by older (defective) logic are never served as current.
VERIFICATION_PIPELINE_VERSION: str = "v3.0-scope-aware"


class PipelineStageID(str, Enum):

    S01_NORMALIZER = "s01_normalizer"
    S02_CACHE_LOOKUP = "s02_cache_lookup"
    S03_QUERY_GENERATOR = "s03_query_generator"
    S04_SOURCE_SEARCH = "s04_source_search"
    S05_EVIDENCE_RETRIEVAL = "s05_evidence_retrieval"
    S06_ARTICLE_EXTRACTOR = "s06_article_extractor"
    S07_EVIDENCE_RANKER = "s07_evidence_ranker"
    S08_SIMILARITY_ANALYZER = "s08_similarity_analyzer"
    S09_CONTRADICTION_DETECTOR = "s09_contradiction_detector"
    S10_MANIPULATION_DETECTOR = "s10_manipulation_detector"
    S11_CLASSIFIER = "s11_classifier"
    S12_PERSISTENCE = "s12_persistence"


KNOWN_SOURCE_ALIASES: dict[str, str] = {
    "প্রথম আলো": "prothomalo.com",
    "prothom alo": "prothomalo.com",
    "prothomalo": "prothomalo.com",
    "prothom-alo": "prothomalo.com",
    "বাংলাদেশ প্রতিদিন": "bd-pratidin.com",
    "bangladesh pratidin": "bd-pratidin.com",
    "bd pratidin": "bd-pratidin.com",
    "bd-pratidin": "bd-pratidin.com",
    "the daily star": "bangla.thedailystar.net",
    "daily star": "bangla.thedailystar.net",
    "dailystar": "bangla.thedailystar.net",
    "যুগান্তর": "jugantor.com",
    "jugantor": "jugantor.com",
    "ইত্তেফাক": "ittefaq.com.bd",
    "ittefaq": "ittefaq.com.bd",
    "কালের কণ্ঠ": "kalerkantho.com",
    "kaler kantho": "kalerkantho.com",
    "kalerkantho": "kalerkantho.com",
    "সমকাল": "samakal.com",
    "samakal": "samakal.com",
    "মানবজমিন": "mzamin.com",
    "manab zamin": "mzamin.com",
    "manabzamin": "mzamin.com",
    "manabzamin.com": "mzamin.com",
    "mzamin": "mzamin.com",
    "ইনকিলাব": "dailyinqilab.com",
    "inqilab": "dailyinqilab.com",
    "daily inqilab": "dailyinqilab.com",
    "dailyinqilab": "dailyinqilab.com",
    "নয়া দিগন্ত": "dailynayadiganta.com",
    "naya diganta": "dailynayadiganta.com",
    "nayadiganta": "dailynayadiganta.com",
    "daily nayadiganta": "dailynayadiganta.com",
    "বাংলা ট্রিবিউন": "banglatribune.com",
    "bangla tribune": "banglatribune.com",
    "dhaka tribune": "dhakatribune.com",
    "dhakatribune": "dhakatribune.com",
    "bdnews24": "bdnews24.com",
    "বিডিনিউজ২৪": "bdnews24.com",
    "rtv": "rtvonline.com",
    "আরটিভি": "rtvonline.com",
    "somoy tv": "somoynews.tv",
    "সময় টিভি": "somoynews.tv",
    "channel 24": "channel24bd.tv",
    "চ্যানেল ২৪": "channel24bd.tv",
}


MAX_SEARCH_QUERIES: int = 10


MAX_CONCURRENT_FETCHES: int = 10


MAX_EVIDENCE_CANDIDATES: int = 5


MIN_KEYWORD_OVERLAP: float = 0.10


REDIS_KEY_PREFIX: str = "bgf"
