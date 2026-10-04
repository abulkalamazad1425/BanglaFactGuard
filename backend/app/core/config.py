from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class DatabaseSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    name: str = Field(default="bangla_fact_guard", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="postgres", description="Database password")
    pool_size: int = Field(default=10, description="SQLAlchemy connection pool size")
    max_overflow: int = Field(
        default=20, description="SQLAlchemy max overflow connections"
    )
    pool_timeout: int = Field(
        default=30, description="Connection pool checkout timeout (s)"
    )
    echo_sql: bool = Field(
        default=False, description="Log all SQL statements (dev only)"
    )

    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str | None = Field(default=None)
    decode_responses: bool = Field(
        default=False, description="Keep bytes for msgpack support"
    )
    max_connections: int = Field(default=50)

    ttl_claim_result: int = Field(
        default=86_400, description="24 h — full VerificationResponse"
    )
    ttl_not_found_result: int = Field(
        default=3_600,
        description=(
            "1 h — freshness of a Source NOT_FOUND result. Shorter than "
            "ttl_claim_result because an outlet can publish (or index) the "
            "story after the first check. Enforced in Redis AND in the "
            "database fallback."
        ),
    )
    ttl_search_result: int = Field(
        default=21_600, description="6 h — raw search URL lists"
    )
    ttl_article_content: int = Field(
        default=43_200, description="12 h — extracted article body"
    )
    ttl_embedding: int = Field(
        default=172_800, description="48 h — LaBSE embedding vectors"
    )
    ttl_nli_output: int = Field(default=172_800, description="48 h — NLI score triples")
    ttl_source_lookup: int = Field(
        default=604_800, description="7 d — resolved canonical domain"
    )

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class MLSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="ML_")

    embedding_model_name: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        description="HuggingFace model name for semantic similarity",
    )
    embedding_batch_size: int = Field(default=32)
    embedding_max_seq_length: int = Field(default=512)
    embedding_thread_workers: int = Field(
        default=4, description="Thread pool workers for embedding encoding"
    )

    nli_model_name: str = Field(
        default="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        description=(
            "HuggingFace model name for NLI-based contradiction detection. "
            "Must be a genuinely multilingual NLI model — cross-encoder/"
            "nli-deberta-v3-* is English-only (MNLI/SNLI/FEVER fine-tuned on "
            "an English-only DeBERTa-v3 vocabulary) and fragments Bangla "
            "input into near-single-character tokens, making its scores "
            "meaningless for Bangla claims. See docs/06-ai-engineering-"
            "design.md S09 for the tokenization evidence."
        ),
    )
    nli_thread_workers: int = Field(
        default=2, description="Thread pool workers for NLI prediction"
    )

    ner_model_name: str = Field(
        default="neuropark/sahajBERT-NER",
        description=(
            "Bangla-specific NER model (PER/LOC/ORG). csebuetnlp/banglabert "
            "is an ELECTRA *pretraining* checkpoint with no token-"
            "classification head — loading it via the HF `ner` pipeline "
            "silently initialises a random, untrained 2-label classifier "
            "that never emits PER/LOC/ORG, so extract_entities() always "
            "returned []. See docs/06-ai-engineering-design.md S08/S10."
        ),
    )
    ner_thread_workers: int = Field(
        default=2, description="Thread pool workers for NER extraction"
    )

    max_ranked_articles: int = Field(
        default=5,
        description="Maximum number of ranked evidence articles to keep",
    )
    min_rank_score: float = Field(
        default=0.05,
        description="Minimum composite rank score required to keep an article",
    )

    device: str = Field(
        default="cpu",
        description="Compute device: 'cpu', 'cuda', or 'cuda:0'",
    )
    use_fp16: bool = Field(
        default=False, description="Use float16 inference (GPU only)"
    )

    cache_dir: str = Field(
        default=os.path.join(
            os.path.expanduser("~"), ".cache", "bangla_fact_guard", "models"
        ),
        description="Local directory for downloaded HuggingFace models",
    )
    load_models_on_startup: bool = Field(
        default=True,
        description="Whether to load ML models into memory on application startup",
    )

    @property
    def max_text_chars_for_embedding(self) -> int:
        return self.embedding_max_seq_length


class MultimodalSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="MULTIMODAL_", protected_namespaces=("settings_",)
    )

    model_dir: str = Field(
        default=os.path.join(
            os.path.expanduser("~"), ".cache", "bangla_fact_guard", "multimodal_model"
        ),
        description="Directory containing img_backbone.pt, text_backbone.pt, classifier.pt, and tokenizer/",
    )

    text_model_name: str = Field(
        default="csebuetnlp/banglabert",
        description="HuggingFace model ID used as BanglaBERT backbone",
    )
    image_model_name: str = Field(
        default="efficientnet_b4",
        description="timm model name for the EfficientNet backbone",
    )
    max_seq_length: int = Field(
        default=128,
        description="Max tokenizer length; must match training max_seq_length",
    )
    img_size: int = Field(
        default=380,
        description="Image resize target; must match training img_size",
    )
    num_classes: int = Field(default=2)
    dropout: float = Field(default=0.4)

    device: str = Field(
        default="cpu",
        description="Compute device for inference: 'cpu' or 'cuda'",
    )
    load_on_startup: bool = Field(
        default=True,
        description="Load model weights during FastAPI lifespan startup",
    )
    inference_thread_workers: int = Field(
        default=2,
        description="ThreadPoolExecutor workers for CPU-bound inference calls",
    )
    model_version: str = Field(
        default="banglabert_efficientnetb4_v1",
        description="Version tag stored with each prediction for traceability",
    )

    text_sim_threshold: float = Field(
        default=0.92,
        description="Min BanglaBERT [CLS] cosine similarity to consider texts identical",
    )
    image_sim_threshold: float = Field(
        default=0.85,
        description="Min EfficientNet feature cosine similarity to consider images identical",
    )
    combined_sim_threshold: float = Field(
        default=0.90,
        description="Min combined-embedding cosine similarity (primary pre-filter)",
    )
    dedup_candidate_limit: int = Field(
        default=100,
        description="Max recent predictions to fetch from DB for similarity search",
    )


class OcrSettings(BaseSettings):
    """Photo-card OCR configuration.

    Two engines are supported. Neither is imported at module load — the
    service probes them lazily so the app still boots when only one (or
    neither) is installed:

      * ``tesseract``  — pytesseract + the ``ben`` traineddata. Best accuracy
        on printed Bangla photo cards, but needs the Tesseract binary.
      * ``easyocr``    — pure-pip, reuses the torch install already required
        by the ML stack. Slower and needs a one-off model download.
    """

    model_config = SettingsConfigDict(env_prefix="OCR_")

    engine: Literal["auto", "tesseract", "easyocr"] = Field(
        default="auto",
        description="'auto' prefers Tesseract and falls back to EasyOCR",
    )

    tesseract_cmd: str = Field(
        default="",
        description=(
            "Absolute path to the tesseract binary. Leave empty when it is on "
            r"PATH. Typical Windows value: C:\Program Files\Tesseract-OCR\tesseract.exe"
        ),
    )
    tesseract_lang: str = Field(
        default="ben",
        description="Tesseract language code(s). 'ben' = Bangla traineddata.",
    )
    tesseract_psm_modes: list[int] = Field(
        default=[6, 4, 3],
        description=(
            "Page segmentation modes to try. 6 = uniform block (typical photo "
            "card), 4 = variable-size columns, 3 = fully automatic."
        ),
    )

    easyocr_languages: list[str] = Field(
        default=["bn"],
        description="EasyOCR language list. 'bn' is the Bangla recogniser.",
    )
    easyocr_use_gpu: bool = Field(default=False)

    thread_workers: int = Field(
        default=2, description="Thread pool workers for blocking OCR calls"
    )
    load_on_startup: bool = Field(
        default=False,
        description=(
            "Initialise the OCR engine during app startup. EasyOCR downloads "
            "~100 MB of weights on first load, so this is off by default and "
            "the engine is initialised on the first request instead."
        ),
    )

    max_image_bytes: int = Field(default=10 * 1024 * 1024)
    upscale_min_width: int = Field(
        default=1600,
        description="Small photo cards are upscaled to at least this width before OCR",
    )
    max_dimension: int = Field(
        default=4000, description="Images larger than this are downscaled before OCR"
    )

    min_line_bangla_ratio: float = Field(
        default=0.45,
        description=(
            "A recognised line is dropped as non-Bangla noise when fewer than "
            "this fraction of its letters are Bangla. Keeps English watermarks, "
            "handles and URLs out of the claim."
        ),
    )
    min_line_confidence: float = Field(
        default=0.30,
        description="Lines recognised below this confidence are dropped as OCR noise",
    )
    source_match_threshold: float = Field(
        default=0.82,
        description=(
            "Minimum fuzzy similarity for an OCR fragment to be accepted as a "
            "verified-source mention. OCR routinely garbles one or two Bangla "
            "glyphs, so exact matching alone misses real banners."
        ),
    )
    source_autoselect_threshold: float = Field(
        default=0.90,
        description="Detected source is pre-selected for the user above this confidence",
    )


class MinioSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = Field(
        default="localhost:9000",
        description="MinIO server host:port (no http/https prefix)",
    )
    access_key: str = Field(
        default="minioadmin",
        description="MinIO access key (root user)",
    )
    secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key (root password)",
    )
    bucket_name: str = Field(
        default="bangla-fact-guard",
        description="Bucket where multimodal submission images are stored",
    )
    secure: bool = Field(
        default=False,
        description="Use HTTPS when connecting to MinIO",
    )
    presigned_url_expiry_seconds: int = Field(
        default=3600,
        description="Pre-signed URL validity period in seconds (default: 1 hour)",
    )


class SearchSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    newsdata_api_key: str = Field(
        default="",
        description="API key for NewsData.io",
    )
    newsdata_base_url: str = Field(
        default="https://newsdata.io/api/1/latest",
        description="NewsData.io latest news API endpoint",
    )
    newsdata_timeout_seconds: int = Field(default=15)
    newsdata_max_results: int = Field(default=10)

    google_cse_api_key: str = Field(
        default="",
        description="API key for Google Custom Search",
    )
    google_cse_cx: str = Field(
        default="",
        description="Search Engine ID (cx) for Google Custom Search",
    )
    google_cse_base_url: str = Field(
        default="https://customsearch.googleapis.com/customsearch/v1",
        description="Google Custom Search JSON API endpoint",
    )
    google_cse_timeout_seconds: int = Field(default=15)
    google_cse_max_results: int = Field(default=10)

    pygooglenews_timeout_seconds: int = Field(default=15)
    pygooglenews_max_results: int = Field(default=10)

    top_k_candidates: int = Field(
        default=15,
        description="Maximum number of candidate article URLs to fetch per claim (increased for parallel search)",
    )
    min_body_length_chars: int = Field(
        default=100,
        description="Minimum extracted body length to consider an article valid",
    )


class ClassificationThresholds(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="THRESHOLD_")

    true_threshold: float = Field(default=0.65)
    partial_threshold: float = Field(default=0.45)
    false_threshold: float = Field(default=0.25)

    contradiction_override_threshold: float = Field(default=0.70)
    headline_sim_threshold: float = Field(default=0.55)
    body_sim_high: float = Field(default=0.75)
    body_altered_threshold: float = Field(default=0.50)
    entity_replaced_threshold: float = Field(default=0.45)

    true_min_semantic_similarity: float = Field(default=0.70)
    true_min_entity_match: float = Field(default=0.65)
    true_max_contradiction: float = Field(default=0.20)

    false_min_contradiction: float = Field(default=0.70)

    partial_min_semantic_similarity: float = Field(default=0.40)

    not_found_max_semantic_similarity: float = Field(
        default=0.30,
        description="If best candidate semantic similarity is below this, verdict is NOT_FOUND",
    )

    min_evidence_threshold: float = Field(
        default=0.25,
        description="Articles below this semantic similarity are discarded as evidence",
    )

    body_altered_min_keyword_overlap: float = Field(
        default=0.30,
        description=(
            "Minimum keyword overlap required alongside low semantic similarity "
            "to trigger body_altered flag. Distinguishes 'wrong article retrieved' "
            "(low keyword overlap) from 'article body was altered' (topic matches "
            "but content differs)."
        ),
    )
    nli_temperature: float = Field(
        default=1.5,
        description=(
            "Temperature scaling factor for NLI probability calibration. "
            "Values > 1.0 flatten overconfident DeBERTa outputs, reducing "
            "false-positive contradiction triggers at the 0.5 soft-penalty "
            "threshold in S11. Set to 1.0 to disable calibration."
        ),
    )
    nli_title_only_attenuation: float = Field(
        default=0.6,
        description=(
            "Multiplier applied to NLI scores when the premise is title-only "
            "(article body absent). Attenuates the signal because title-only "
            "NLI is far less reliable than body-based NLI."
        ),
    )
    # ── source correspondence (does the claimed outlet carry THIS report?) ──
    corr_headline_sim_strong: float = Field(
        default=0.72,
        description="Headline↔source-title similarity at/above which the report corresponds on its own.",
    )
    corr_headline_sim_plausible: float = Field(
        default=0.55,
        description="Minimum headline↔title similarity for a plausible correspondence (needs lexical support).",
    )
    corr_keyword_title_plausible: float = Field(
        default=0.50,
        description="Claim-keyword coverage of the source title that counts as lexical support.",
    )
    corr_keyword_passage_plausible: float = Field(
        default=0.60,
        description="Claim-keyword coverage of the relevant passages that counts as lexical support.",
    )
    corr_keyword_only_title: float = Field(
        default=0.70,
        description="Title keyword coverage required when no embedding similarity is available.",
    )
    # ── content support (MATCHED needs positive support, never absence of contradiction) ──
    support_headline_sim: float = Field(default=0.75)
    support_keyword_coverage: float = Field(default=0.70)
    support_keyword_coverage_no_ner: float = Field(
        default=0.85,
        description="Stricter keyword coverage required when entity coverage cannot be computed.",
    )
    support_entity_coverage: float = Field(default=0.80)
    support_body_similarity: float = Field(default=0.70)
    support_body_min_chunk_similarity: float = Field(default=0.50)
    support_body_keyword_coverage: float = Field(default=0.60)
    possible_contradiction: float = Field(
        default=0.50,
        description="NLI contradiction at/above which a possible contradiction blocks MATCHED.",
    )
    nli_bangla_validated: bool = Field(
        default=False,
        description=(
            "Set True only after the NLI model has been evaluated on labelled "
            "Bangla pairs. While False a high NLI contradiction can block "
            "MATCHED but can never, on its own, produce ALTERED."
        ),
    )
    # ── search adequacy ──
    search_min_successful_calls: int = Field(
        default=2,
        description="Minimum completed provider calls (success or successful-empty) for a search to count as adequate.",
    )
    search_min_success_ratio: float = Field(
        default=0.5,
        description="Minimum share of attempted provider calls that must complete for adequacy.",
    )

    max_single_dimension_weight: float = Field(
        default=0.65,
        description=(
            "Maximum effective weight any single score dimension can receive "
            "after re-normalisation when other dimensions are missing. Prevents "
            "a single dimension (e.g. semantic_similarity at 0.45/0.45 = 1.0 "
            "effective weight) from unilaterally driving the verdict."
        ),
    )

    @property
    def contradiction_threshold(self) -> float:
        return self.contradiction_override_threshold


class AuthSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_STRONG_RANDOM_SECRET_32CHARS",
        description="HS256 signing key for JWT tokens. Must be at least 32 characters in production.",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_ttl_seconds: int = Field(
        default=900,
        description="Access token time-to-live in seconds",
    )
    refresh_token_ttl_seconds: int = Field(
        default=604_800,
        description="Refresh token time-to-live in seconds",
    )
    bcrypt_rounds: int = Field(
        default=12,
        description="bcrypt work factor (cost). Higher = slower but more secure.",
    )
    initial_expert_credibility: float = Field(
        default=0.5,
        description="Credibility score assigned to new expert accounts",
    )
    min_expert_votes_to_finalize: int = Field(
        default=3,
        description="Minimum expert votes required before a claim can be finalized",
    )


class EmailSettings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="EMAIL_")

    smtp_host: str = Field(
        default="",
        description="SMTP server host. Empty disables real email sending — "
        "OTPs are logged to the console instead (local/dev fallback).",
    )
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    use_tls: bool = Field(default=True)
    from_address: str = Field(default="no-reply@banglafactguard.local")
    from_name: str = Field(default="BanglaFactGuard")

    otp_length: int = Field(default=6)
    otp_ttl_minutes: int = Field(default=10)

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host)


class GeminiSettings(BaseSettings):
    """Gemini is used only for photo-card headline extraction.

    Extraction keeps its deterministic fallback. Photo-card content comparison
    uses the locally loaded NLP models and does not depend on these settings.
    """

    model_config = SettingsConfigDict(env_prefix="GEMINI_")

    api_key: str = Field(
        default="",
        description="Gemini API key for headline extraction. Empty uses the deterministic extractor.",
    )
    model_name: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model id used for photo-card headline extraction only.",
    )
    base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Gemini REST API base URL.",
    )
    timeout_seconds: int = Field(
        default=20,
        description="HTTP timeout for a Gemini headline extraction call.",
    )
    min_grounding_overlap: float = Field(
        default=0.5,
        description=(
            "Minimum fraction of the extracted headline's significant words "
            "that must actually appear in the OCR text for the extraction to "
            "be trusted. Below this, Gemini's output is treated as "
            "ungrounded/hallucinated and discarded in favour of the "
            "deterministic fallback — this is also the mechanical backstop "
            "against prompt injection embedded in OCR'd text: even if "
            "injected instructions change what Gemini returns, an "
            "ungrounded headline fails this check regardless of why it "
            "diverged from the source text."
        ),
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-gemini-api-key-here"


class JobSettings(BaseSettings):
    """Background verification worker (see app/features/verification/jobs.py)."""

    model_config = SettingsConfigDict(env_prefix="JOBS_")

    enabled: bool = Field(default=True, description="Run the in-process job worker.")
    max_concurrent: int = Field(
        default=2,
        ge=1,
        description="Bound on simultaneously running verification jobs (the pipeline has CPU-bound stretches that share the API event loop).",
    )
    poll_interval_seconds: float = Field(default=5.0, gt=0)
    stale_after_seconds: float = Field(
        default=120.0,
        gt=0,
        description="A RUNNING job with no heartbeat for this long is reclaimed (restart recovery latency).",
    )
    heartbeat_interval_seconds: float = Field(default=30.0, gt=0)


class AppSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="BanglaFactGuard")
    app_version: str = Field(default="0.1.0")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    debug: bool = Field(default=False)
    api_v1_prefix: str = Field(default="/api/v1")
    cors_origins: list[str] = Field(
        default=["*"],
        description="List of origins allowed to make CORS requests",
    )

    api_key_header: str = Field(default="X-API-Key")
    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_STRONG_RANDOM_SECRET",
        description="Used for signing tokens (future auth)",
    )

    log_level: str = Field(default="INFO", description="Root log level")
    log_format: Literal["json", "console"] = Field(
        default="json",
        description="'json' for production, 'console' for local dev",
    )

    request_timeout_seconds: int = Field(default=120)
    max_headline_length: int = Field(default=2000)
    max_body_length: int = Field(default=50_000)

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    thresholds: ClassificationThresholds = Field(
        default_factory=ClassificationThresholds
    )
    multimodal: MultimodalSettings = Field(default_factory=MultimodalSettings)
    ocr: OcrSettings = Field(default_factory=OcrSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    jobs: JobSettings = Field(default_factory=JobSettings)

    @property
    def classification(self) -> ClassificationThresholds:
        return self.thresholds

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}, got {v!r}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
