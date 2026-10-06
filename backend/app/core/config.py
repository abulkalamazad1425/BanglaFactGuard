from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
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
        default="arafatfahim/BanglaTag",
        description=(
            "BanglaBERT (csebuetnlp/banglabert) fine-tuned for NER. "
            "Use a trained token-classification checkpoint with PER/LOC/ORG "
            "labels, not the base ELECTRA pretraining model."
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


class PhotocardSettings(BaseSettings):
    """Photo-card upload limits. The card is read by Gemini only
    (see GeminiSettings); there is no OCR engine."""

    model_config = SettingsConfigDict(env_prefix="PHOTOCARD_")

    max_image_bytes: int = Field(default=10 * 1024 * 1024)


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
    """Source-correspondence and search-adequacy thresholds.

    The Headline Alteration verdict has its own documented constants in
    `analysis/headline_comparison.py`; body similarity has no thresholds at
    all (it produces measurements only, never a verdict).
    """

    model_config = SettingsConfigDict(env_prefix="THRESHOLD_")

    # ── source correspondence (does the claimed outlet carry THIS report?) ──
    corr_headline_sim_alone: float = Field(
        default=0.85,
        description="Headline/source-title similarity at/above which the report corresponds without further lexical support (near-identical wording).",
    )
    corr_headline_sim_strong: float = Field(
        default=0.72,
        description="Headline/title similarity that corresponds strongly when the claim's keywords also appear in the title.",
    )
    corr_headline_sim_plausible: float = Field(
        default=0.55,
        description="Minimum headline/title similarity for a plausible correspondence (needs lexical support).",
    )
    corr_keyword_title_plausible: float = Field(
        default=0.50,
        description="Claim-keyword coverage of the source title that counts as lexical support.",
    )
    corr_keyword_passage_plausible: float = Field(
        default=0.60,
        description="Claim-keyword coverage of the source passages discussing the claim that counts as lexical support.",
    )
    corr_keyword_only_title: float = Field(
        default=0.70,
        description="Title keyword coverage required when no embedding similarity is available.",
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
        default=31_536_000,
        description=(
            "Refresh token time-to-live in seconds (default 365 days). Every "
            "refresh issues a new token with a fresh lifetime, so a session "
            "lasts until the user logs out (or is inactive for this long)."
        ),
    )
    refresh_rotation_grace_seconds: int = Field(
        default=120,
        ge=0,
        description=(
            "How long a just-rotated refresh token stays usable. Covers a "
            "refresh response that never reached the client (network drop, "
            "sleeping tab) so the user is not logged out. Logout still "
            "revokes immediately."
        ),
    )
    bcrypt_rounds: int = Field(
        default=12,
        description="bcrypt work factor (cost). Higher = slower but more secure.",
    )
    initial_expert_credibility: float = Field(
        default=0.5,
        description="Deprecated compatibility setting; new expert credibility is uncalculated until activation",
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
    website_url: str = Field(default="http://localhost:4200", pattern=r"^https?://[^\s]+$")

    otp_length: int = Field(default=6)
    otp_ttl_minutes: int = Field(default=10)

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host)


class GeminiSettings(BaseSettings):
    """Gemini is the ONLY photo-card extractor: it reads the headline, the
    claimed news outlet (matched against the active verified sources) and the
    published date from the ORIGINAL image. There is no OCR fallback.

    Attempts are made in batches: ``attempts_per_batch`` requests, then a
    ``batch_pause_seconds`` pause, up to ``batches`` batches. With the
    defaults that is at most 3 x 3 = 9 requests in total, the first request
    included; the first success stops the loop.
    """

    model_config = SettingsConfigDict(env_prefix="GEMINI_")

    api_key: str = Field(
        default="",
        description="Gemini API key for photo-card extraction. Without any key photo cards cannot be processed.",
    )
    api_keys: list[str] = Field(
        default_factory=lambda: _numbered_gemini_keys(),
        description=(
            "Further keys, rotated when one reaches its limit. Read from GEMINI_API_KEY1, "
            "GEMINI_API_KEY2, ... (any number, in numeric order)."
        ),
    )
    model_name: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model id used for photo-card image extraction only.",
    )
    base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Gemini REST API base URL.",
    )
    timeout_seconds: int = Field(
        default=20,
        description="HTTP timeout for ONE Gemini extraction attempt.",
    )
    attempts_per_batch: int = Field(
        default=3,
        ge=1,
        le=3,
        description="Requests per batch (never more than 3).",
    )
    batches: int = Field(
        default=3,
        ge=1,
        le=3,
        description="Batches per card (never more than 3): at most 9 requests in total.",
    )
    batch_pause_seconds: float = Field(
        default=10.0,
        ge=0.0,
        description="Pause after a batch in which every attempt failed, before the next batch.",
    )
    retry_base_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Exponential backoff base between attempts inside one batch (1s, 2s).",
    )

    @property
    def max_requests(self) -> int:
        return self.attempts_per_batch * self.batches

    @property
    def all_api_keys(self) -> list[str]:
        """GEMINI_API_KEY first, then the numbered keys; blanks, placeholders
        and duplicates removed. This is the rotation order."""
        keys: list[str] = []
        for key in (self.api_key, *self.api_keys):
            key = (key or "").strip()
            if key and key != "your-gemini-api-key-here" and key not in keys:
                keys.append(key)
        return keys

    @property
    def is_configured(self) -> bool:
        return bool(self.all_api_keys)


_NUMBERED_KEY_RE = re.compile(r"GEMINI_API_KEY_?(\d+)", re.IGNORECASE)


def _numbered_gemini_keys() -> list[str]:
    found = []
    for name, value in os.environ.items():
        m = _NUMBERED_KEY_RE.fullmatch(name)
        if m and value.strip():
            found.append((int(m.group(1)), value.strip()))
    return [value for _, value in sorted(found)]


class JobSettings(BaseSettings):
    """Background verification worker (see app/features/verification/jobs.py)."""

    model_config = SettingsConfigDict(env_prefix="JOBS_")

    enabled: bool = Field(default=True, description="Run the in-process job worker.")
    max_concurrent: int = Field(
        default=2,
        ge=1,
        description="Bound on simultaneously running verification jobs (the pipeline has CPU-bound stretches that share the API event loop).",
    )
    photocard_max_concurrent: int = Field(
        default=4,
        ge=1,
        description=(
            "Separate bound for photo-card jobs. They run in their own lane so a card "
            "waiting out Gemini retries never delays text or text & image jobs."
        ),
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
    photocard: PhotocardSettings = Field(default_factory=PhotocardSettings)
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
