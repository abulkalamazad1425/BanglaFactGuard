from __future__ import annotations

from enum import Enum


class VerificationLabel(str, Enum):

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
    "the daily star": "thedailystar.net",
    "daily star": "thedailystar.net",
    "dailystar": "thedailystar.net",
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
