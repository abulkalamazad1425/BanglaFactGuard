"""
app/core/constants.py
=====================
Domain-level enumerations, label definitions, and shared constant values
for BanglaFactGuard.

Design decisions:
- All enums derive from `str, Enum` so they serialise cleanly to JSON
  (Pydantic, FastAPI responses, and structlog all handle str enums natively).
- Provider and stage names are also enums to prevent typo-driven bugs
  in Redis key construction and database ENUM columns.
- Threshold defaults are defined here only as documentation references;
  the canonical values live in `core/config.py` so they are env-overridable.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Verdict Labels
# ---------------------------------------------------------------------------


class VerificationLabel(str, Enum):
    """
    Final verdict labels produced by Stage 11 (Classifier).

    Semantics:
        TRUE                      — Claimed source verifiably published the article
                                    with matching content.
        FALSE                     — Source exists but content significantly contradicts
                                    the claim (fabricated / disinformation).
        PARTIALLY_TRUE            — Evidence found but headline, numbers, or entities
                                    were altered / selectively presented.
        NOT_FOUND_IN_CLAIMED_SOURCE — No article matching the claim was found in the
                                    claimed source within the retrieval budget.
    """

    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    NOT_FOUND_IN_CLAIMED_SOURCE = "NOT_FOUND_IN_CLAIMED_SOURCE"


# ---------------------------------------------------------------------------
# Claim / Pipeline Status
# ---------------------------------------------------------------------------


class ClaimStatus(str, Enum):
    """Lifecycle state of a verification request stored in `verified_claims`."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Search Providers
# ---------------------------------------------------------------------------


class SearchProvider(str, Enum):
    """
    External search providers used in Stage 4 (Source-Constrained Search).
    Order implies priority: Brave > Google RSS > DuckDuckGo.
    """

    BRAVE = "brave"
    GOOGLE_RSS = "google_rss"
    DDG = "ddg"


# ---------------------------------------------------------------------------
# Search Query Types
# ---------------------------------------------------------------------------


class QueryType(str, Enum):
    """
    Types of search queries generated in Stage 3 (Query Generator).
    Each type targets a different retrieval signal.
    """

    HEADLINE = "headline"                  # Raw headline query
    KEYWORDS = "keywords"                  # Extracted TF-IDF / YAKE keywords
    ENTITIES = "entities"                  # Headline + named entities
    DATE_BOUND = "date_bound"              # Headline + published_date constraint
    BODY_SUMMARY = "body_summary"          # Summarised body keywords


# ---------------------------------------------------------------------------
# Extraction Methods
# ---------------------------------------------------------------------------


class ExtractionMethod(str, Enum):
    """Article extraction backend used in Stage 6."""

    TRAFILATURA = "trafilatura"
    BEAUTIFULSOUP = "beautifulsoup"


# ---------------------------------------------------------------------------
# NLI Output Labels
# ---------------------------------------------------------------------------


class NLILabel(str, Enum):
    """
    Labels produced by the cross-encoder NLI model (Stage 9).
    Maps to standard textual-entailment terminology.
    """

    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Manipulation Types
# ---------------------------------------------------------------------------


class ManipulationType(str, Enum):
    """
    Categories of manipulation detected in Stage 10.
    A single article comparison may trigger multiple types.
    """

    HEADLINE_MANIPULATED = "headline_manipulated"   # Body matches; headline does not
    BODY_ALTERED = "body_altered"                   # Body significantly diverges
    NUMBERS_ALTERED = "numbers_altered"             # Numbers swapped / inflated
    ENTITIES_REPLACED = "entities_replaced"         # Named entities substituted


# ---------------------------------------------------------------------------
# Verification Log Levels
# ---------------------------------------------------------------------------


class LogLevel(str, Enum):
    """Severity levels stored in the `verification_logs` table."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Pipeline Stage Identifiers
# ---------------------------------------------------------------------------


class PipelineStageID(str, Enum):
    """
    Canonical identifiers for each of the 12 pipeline stages.
    Used as the `stage` column value in `verification_logs` and for
    structured log context.
    """

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


# ---------------------------------------------------------------------------
# Source Normalisation Map
# ---------------------------------------------------------------------------


# Static mapping of common Bangla/transliterated source aliases to their
# canonical domain names.  The source_registry DB table extends this at runtime.
KNOWN_SOURCE_ALIASES: dict[str, str] = {
    # Prothom Alo
    "প্রথম আলো": "prothomalo.com",
    "prothom alo": "prothomalo.com",
    "prothomalo": "prothomalo.com",
    "prothom-alo": "prothomalo.com",
    # The Daily Star
    "the daily star": "thedailystar.net",
    "daily star": "thedailystar.net",
    "dailystar": "thedailystar.net",
    # Jugantor
    "যুগান্তর": "jugantor.com",
    "jugantor": "jugantor.com",
    # Ittefaq
    "ইত্তেফাক": "ittefaq.com.bd",
    "ittefaq": "ittefaq.com.bd",
    # Kaler Kantho
    "কালের কণ্ঠ": "kalerkantho.com",
    "kaler kantho": "kalerkantho.com",
    "kalerkantho": "kalerkantho.com",
    # Samakal
    "সমকাল": "samakal.com",
    "samakal": "samakal.com",
    # Manab Zamin
    "মানবজমিন": "mzamin.com",
    "manab zamin": "mzamin.com",
    "mzamin": "mzamin.com",
    # Bangla Tribune
    "বাংলা ট্রিবিউন": "banglatribune.com",
    "bangla tribune": "banglatribune.com",
    # Dhaka Tribune
    "dhaka tribune": "dhakatribune.com",
    "dhakatribune": "dhakatribune.com",
    # bdnews24
    "bdnews24": "bdnews24.com",
    "বিডিনিউজ২৪": "bdnews24.com",
    # RTV
    "rtv": "rtvonline.com",
    "আরটিভি": "rtvonline.com",
    # Somoy TV
    "somoy tv": "somoynews.tv",
    "সময় টিভি": "somoynews.tv",
    # Channel 24
    "channel 24": "channel24bd.tv",
    "চ্যানেল ২৪": "channel24bd.tv",
}

# ---------------------------------------------------------------------------
# Miscellaneous Numeric Constants
# ---------------------------------------------------------------------------

# Maximum number of search queries generated per claim (Stage 3)
MAX_SEARCH_QUERIES: int = 5

# Maximum concurrent HTTP requests during evidence retrieval (Stage 5)
MAX_CONCURRENT_FETCHES: int = 10

# Maximum candidate articles passed to similarity analysis (Stage 8)
MAX_EVIDENCE_CANDIDATES: int = 5

# Minimum Jaccard keyword overlap to consider an article relevant
MIN_KEYWORD_OVERLAP: float = 0.10

# Redis key prefix namespace
REDIS_KEY_PREFIX: str = "bgf"
