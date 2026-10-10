# Backend Codebase Guide: কোন file কী কাজ করে

> **তারিখ:** 2026-10-07 · **পরিধি:** `backend/` এর প্রতিটি file
> এই document এ code এখন যেমন আছে তেমনটাই বর্ণনা করা হয়েছে। কী পরিবর্তন করা উচিত, তা আলাদা document এ আছে: [`backend-cleanup-and-refactoring-audit.md`](backend-cleanup-and-refactoring-audit.md)।

---

## সূচিপত্র

1. [বড় চিত্র: system টি কী করে](#1-বড়-চিত্র-system-টি-কী-করে)
2. [Request এর প্রবাহ](#2-request-এর-প্রবাহ)
3. [Root file](#3-root-file-backend)
4. [`app/` entry point ও `api/`](#4-app-entry-point-ও-api)
5. [`app/core/`](#5-appcore)
6. [`app/db/` ও migration](#6-appdb-ও-migration)
7. [`app/shared/`](#7-appshared)
8. [Feature package (`app/features/`)](#8-feature-package-appfeatures)
9. [Verification pipeline (S01–S13)](#9-verification-pipeline-s01s13)
10. [`scripts/`](#10-scripts)
11. [`tests/`](#11-tests)
12. [Database table ও তাদের মালিক](#12-database-table-ও-তাদের-মালিক)

---

## 1. বড় চিত্র: system টি কী করে

BanglaFactGuard একটি **FastAPI** backend। এটি বাংলা খবরের দাবি যাচাই করে, তিনভাবে:

| যাচাইয়ের ধরন | Input | যা ঘটে |
|---|---|---|
| **SOURCE_BASED** (text) | শিরোনাম, দাবিকৃত সংবাদমাধ্যম, ঐচ্ছিক body ও তারিখ | ১৩ ধাপের pipeline দাবিকৃত সংবাদমাধ্যমে সংশ্লিষ্ট খবর খোঁজে, এবং তিনটি স্বাধীন ফলাফল দেয়: **source** (খবরটি পাওয়া গেছে কিনা), **headline alteration** (শিরোনাম বদলানো হয়েছে কিনা), **date** (তারিখ মেলে কিনা)। body দিলে চারটি similarity score ও পাওয়া যায়। |
| **PHOTO_CARD** | শুধু একটি ছবি | Gemini ছবি থেকে শিরোনাম, সংবাদমাধ্যম ও ছাপা তারিখ পড়ে। এরপর SOURCE_BASED এর একই pipeline চলে, তবে শুধু শিরোনাম দিয়ে (HEADLINE_ONLY)। |
| **MULTIMODAL** | শিরোনাম, body ও ছবি | BanglaBERT + EfficientNet-B4 model দিয়ে FAKE/NON_FAKE এর একটি প্রাথমিক অনুমান দেয়। একই রকম আগের submission থাকলে নতুন inference না চালিয়ে সেই ফলাফল আবার ব্যবহার করে। |

যেকোনো পদ্ধতিতে যাচাই হোক, **চূড়ান্ত রায় (Overall: FAKE/REAL/MISLEADING/ALTERED) সবসময় মানুষ দেয়।** expert রা credibility-weighted vote দেন। নির্দিষ্ট সময় বা vote সংখ্যার মধ্যে ঐকমত্য না হলে claim টি admin এর কাছে যায় (escalate), এবং admin এর সিদ্ধান্তই চূড়ান্ত। automated system কখনো overall verdict দেয় না।

**ব্যবহৃত প্রযুক্তি:** FastAPI, SQLAlchemy 2 (async, asyncpg), PostgreSQL, Alembic, Redis (cache pointer ও search cache), MinIO (ছবি রাখার জন্য), structlog, sentence-transformers (LaBSE, cross-encoder), HuggingFace (mDeBERTa NLI, BanglaTag NER), torch/timm (multimodal), trafilatura/readability/BeautifulSoup (article extraction), pygooglenews + Playwright (search), Google Gemini REST API (photo card পড়ার জন্য), SMTP (email)।

**Background কাজের জন্য তিনটি worker** একই process এর ভেতরে asyncio task হিসেবে চলে (`core/lifespan.py` থেকে চালু হয়):
1. `VerificationJobWorker`: DB তে জমা থাকা job চালায় (text, photo card, multimodal)।
2. `ResultDeliveryWorker`: submitter কে in-app notification ও ফলাফলের email পাঠায়।
3. `EscalationWorker`: সময়সীমা পার হওয়া claim খুঁজে admin এর কাছে পাঠায়।

---

## 2. Request এর প্রবাহ

### 2.1 Text claim (`POST /api/v1/verify/async`)
```
router (verification/router.py)
 └─ VerificationService.register_claim
     ├─ resolve_claimed_source  ── না পেলে 404
     ├─ compute_claim_hash (identity)
     ├─ ResultReuseService.find_reusable ── পেলে: নিজের submission এ ফলাফল copy + notification, শেষ
     ├─ একই submitter এর একই claim চলমান থাকলে সেটাই ফেরত দেয়
     └─ নতুন Submission(PENDING, phase=QUEUED) + VerificationJob, commit, 202
VerificationJobWorker (verification/jobs.py)
 └─ execute_job(kind=SOURCE_BASED) → VerificationService.run_for_submission → verify()
     └─ PipelineOrchestrator.run(S01…S13)  → S13 result লেখে, EXPERT_REVIEW এ পাঠায়, notification দেয়
client poll করে: GET /verify/{id}/status  →  GET /verify/{id}
```

### 2.2 Photo card (`POST /api/v1/photocard/verify/async`)
```
router → PhotoCardService.accept_upload: ছবি MinIO তে → Submission(PENDING, headline=None) + PhotocardExtraction(PENDING) + Job → 202
worker → PhotoCardService.process_submission
   ├─ phase=EXTRACTING, ছবি download
   ├─ PhotocardClaimExtractor (Gemini, সর্বোচ্চ ৯টি request) → headline + active source + তারিখ
   │     ব্যর্থ হলে → PermanentJobError → submission FAILED (কারণসহ)
   ├─ submission এ headline/source/date বসানো, photo card এর নিজস্ব identity hash
   └─ build_photocard_stages (S01 এর জায়গায় PhotocardNormalizerStage) → orchestrator
client: GET /photocard/{id}
```

### 2.3 Multimodal (`POST /api/v1/multimodal/predict/async`)
```
router → MultimodalPredictionService.accept_upload: ছবি MinIO তে → Submission(PENDING) + Job(payload=image_key) → 202
worker → process_queued → predict(): embedding → আগের প্রায় একই submission খোঁজা (cosine) → না পেলে inference → MultimodalAnalysis → EXPERT_REVIEW
client: GET /submissions/{id} → GET /multimodal/by-submission/{id}
```

### 2.4 Expert review
```
GET /expert/queue  → ExpertReviewService.get_queue (expert: খোলা claim; admin: escalated + খোলা)
POST /expert/queue/{id}/vote → submit_vote: submission row lock → AI এর তখনকার মতামতের snapshot → tier অনুযায়ী weight → ExpertReview
   → _finalize_or_escalate: weighted tally ≥ T, ভোটার ≥ M, ব্যবধান ≥ margin, এবং একক নেতা থাকলে → FINALIZED
                            নাহলে সীমা পার হলে → ESCALATED + admin কে notification
admin এর vote (শুধু ESCALATED claim এ) → সেটাই চূড়ান্ত
ResultDeliveryWorker → "final" notification + email
```

---

## 3. Root file (`backend/`)

| File | কাজ |
|---|---|
| `.env` | local secret ও configuration (git এ রাখা হয় না)। DB, Redis, Gemini key (key rotation এর জন্য একাধিক `GEMINI_API_KEY{n}`), MinIO, SMTP, threshold। এর কিছু variable কোনো setting এ map হয় না (audit section 4 দেখুন)। |
| `.env.example` | নতুন developer এর জন্য template। এটি git এ tracked। |
| `alembic.ini` | Alembic এর configuration। `sqlalchemy.url` ইচ্ছাকৃতভাবে খালি রাখা, এটি `migrations/env.py` এ settings থেকে বসানো হয়। file name এর template: `YYYYMMDD_HHMM_<rev>_<slug>`। |
| `docker-compose.yml` | শুধু Redis 7.2 (AOF, 512 MB LRU) ও MinIO চালায়। PostgreSQL ও app এখানে নেই, Postgres আলাদাভাবে local machine এ চলে। |
| `pyproject.toml` | Package এর metadata, dependency, ruff/mypy/pytest/coverage এর configuration (coverage এর ন্যূনতম সীমা 70%, `asyncio_mode=auto`)। |
| `requirements.txt` | pip দিয়ে install করার জন্য dependency তালিকা (pyproject এর সাথে পুরোপুরি মেলে না)। |
| `run.py` | Development server চালায়: Windows এ Proactor event loop set করে `uvicorn app.main:app --reload` (127.0.0.1:8000)। |
| `coverage.xml`, `.coverage` | pytest-cov এর তৈরি করা report (generated file)। |

---

## 4. `app/` entry point ও `api/`

| File | কাজ |
|---|---|
| `app/__init__.py` | খালি package marker। |
| `app/main.py` | `create_app()`: FastAPI instance তৈরি (title, docs URL, `lifespan`), CORS middleware, `ProcessTimeMiddleware`, `CorrelationIDMiddleware`, `/api/v1` router যোগ করা, exception handler register করা। `import app.shared.models_registry` দিয়ে সব ORM model একবারে load করে, যাতে `relationship("ClassName")` এর মতো string reference resolve হতে পারে। Windows এ event loop policy set করে। |
| `app/api/exception_handlers.py` | দুটি global handler। (১) `BanglaFactGuardError` হলে exception এর `http_status_code` সহ `{"error","message","details","request_id"}`। `TokenExpiredError` কে info level এ log করে (এটা স্বাভাবিক ঘটনা), বাকিগুলো warning level এ। (২) অন্য যেকোনো exception হলে 500 ও একটি সাধারণ message। |
| `app/api/middleware.py` | `CorrelationIDMiddleware`: request থেকে `X-Request-ID` নেয় অথবা নতুন UUID বানায়, `request.state` এ রাখে, response header এ ফেরত দেয়। `ProcessTimeMiddleware`: `X-Process-Time-Ms` header যোগ করে। |
| `app/api/v1/router.py` | `/api/v1` prefix এর অধীনে ১২টি feature router যুক্ত করে: admin, auth, dashboard, expert, health, multimodal, notifications, photocard, sources, submissions, users, verify। |

---

## 5. `app/core/`

| File | কাজ |
|---|---|
| `config.py` | Pydantic-settings দিয়ে লেখা পুরো configuration। `load_dotenv()` চালিয়ে `.env` থেকে মান পড়ে। প্রতিটি group এর আলাদা class ও env prefix আছে: `DatabaseSettings (DB_)` (async ও sync URL তৈরি করে), `RedisSettings (REDIS_)` (TTL গুলো, যার মধ্যে NOT_FOUND ফলাফলের জন্য ছোট TTL), `MLSettings (ML_)` (model এর নাম, thread সংখ্যা, ranker এর সীমা), `MultimodalSettings (MULTIMODAL_)` (model dir, ছবির আকার, dedup threshold), `PhotocardSettings (PHOTOCARD_)` (ছবির সর্বোচ্চ আকার), `MinioSettings (MINIO_)`, `SearchSettings (SEARCH_)`, `ClassificationThresholds (THRESHOLD_)` (source correspondence ও search adequacy এর threshold), `AuthSettings (AUTH_)` (JWT, bcrypt, token TTL, rotation grace; `AUTH_SECRET_KEY` বাধ্যতামূলক, কমপক্ষে ৩২ অক্ষর, না থাকলে app চালু হয় না), `EmailSettings (EMAIL_)` (SMTP; host না দিলে OTP console এ log হয়), `GeminiSettings (GEMINI_)` (key এর তালিকা, batch/attempt এর সীমা, সর্বোচ্চ ৩×৩ request), `JobSettings (JOBS_)` (worker concurrency, poll interval, stale reclaim)। এগুলো সব একসাথে থাকে `AppSettings` এ। `get_settings()` এর ফলাফল `lru_cache` দিয়ে cache করা (singleton)। |
| `constants.py` | পুরো domain এর enum। verification এর ফলাফল: `SourceStatus` (CONFIRMED/NOT_FOUND/INCOMPLETE), `ContentStatus` (MATCHED/ALTERED), `HeadlineAlterationStatus` (EXACT_MATCHED/MEANING_PRESERVED/ALTERED, শুধু দেখানোর জন্য), `HeadlineCheckStatus` (verdict না হলে কারণ), `BodyComparisonStatus`, `DateStatus`। review: `OverallVerdict`, `ExpertVerdict` (legacy)। lifecycle: `SubmissionStatus`, `SubmissionType`, `ClaimScope`, `JobPhase`। pipeline: `SearchProvider`, `QueryType`, `ExtractionMethod`, `MetricState`, `SearchCallOutcome`, `PipelineStageID`। এছাড়া `VERIFICATION_PIPELINE_VERSION`, যা claim identity এর অংশ; এটি বদলালে পুরোনো ফলাফল আর reuse হয় না। আরও আছে `KNOWN_SOURCE_ALIASES` (source এর নাম থেকে domain এর static map)। |
| `exceptions.py` | Domain exception এর hierarchy। প্রতিটি class এর একটি `http_status_code` আছে, যা global handler ব্যবহার করে। প্রধানগুলো: `DomainValidationError(422)`, `SourceNotFoundError(404)`, `ImageStorageUnavailableError(503)`, `PermanentJobError` (এমন job failure যা retry করে ঠিক হবে না, user কে দেখানোর মতো কারণসহ), `PipelineError`/`StageError` ও এর subclass (`NormalizationError`, `QueryGenerationError`, `ClassificationError`, `PersistenceError`), `RecordNotFoundError(404)`, `DuplicateRecordError(409)`, `ExternalAPIError(502)`/`PyGoogleNewsError`, `ModelNotLoadedError`/`InferenceError`, auth এর error (`InvalidCredentialsError`, `TokenExpiredError`, `TokenInvalidError`, `OtpInvalidError`, `InactiveAccountError`), `PermissionDeniedError(403)`, `WeakPasswordError`, `EmailDeliveryError(503)`, `OtpGenerationError`। |
| `lifespan.py` | App চালু ও বন্ধ হওয়ার সময়ের কাজ। চালু হলে: logging setup, Redis client ও `CacheService`, shared `httpx.AsyncClient` (100 connection), ML model load (`EmbeddingService`, `NERService`, `NLIService`, যদি `ML_LOAD_MODELS_ON_STARTUP` থাকে, এবং ব্যর্থ হলেও app চালু থাকে), `MultimodalModelLoader`, দুটি MinIO bucket নিশ্চিত করা, তিনটি background worker চালু করা। সব কিছু `app.state` এ রাখা হয়। বন্ধ হলে worker থামায়, HTTP client ও Redis বন্ধ করে, এবং সবশেষে DB engine এর pool বন্ধ করে (`close_engine`), যাতে একই process এ lifespan আবার চালু হতে পারে। |
| `logging.py` | structlog এর configuration (JSON বা console renderer, ISO timestamp)। sqlalchemy, httpx ও uvicorn.access এর log কম দেখায়। `bind_pipeline_context()` pipeline log এ claim_id যোগ করে। |

---

## 6. `app/db/` ও migration

| File | কাজ |
|---|---|
| `db/engine.py` | Import এর সময়েই async engine তৈরি হয় (pool_size, overflow, `pool_pre_ping`, `pool_recycle=1800`, Postgres এর JIT বন্ধ)। `AsyncSessionLocal` (`expire_on_commit=False`, `autoflush=False`) পুরো codebase এর session factory। এছাড়া আছে `get_async_session` (FastAPI dependency, শেষে commit করে, error হলে rollback) ও `close_engine`। |
| `db/migrations/env.py` | Alembic এর runtime। settings থেকে sync URL নেয় এবং `models_registry.Base.metadata` কে target হিসেবে ধরে। `compare_type` ও `compare_server_default` চালু থাকায় autogenerate করলে column type ও default এর পরিবর্তনও ধরা পড়ে। |
| `db/migrations/script.py.mako` | নতুন migration file এর template। |

### Migration এর ইতিহাস (`db/migrations/versions/`)

এগুলো একটির পর একটি chain হিসেবে চলে এবং ক্রম বদলানো যায় না। নিচে প্রতিটির সারসংক্ষেপ:

| Revision | তারিখ | কী করে |
|---|---|---|
| `c64e7a11f599` initial_schema | 06-07 | প্রথম schema: `source_registry`, পুরোনো claim/result/search/article table, এবং সংশ্লিষ্ট enum |
| `31eca564c430`, `c8bfea04d45d` | 06-08 | `search_provider_enum` এ SearXNG ও অন্যান্য search provider যোগ (এগুলো এখন আর ব্যবহার হয় না) |
| `2ece7aa03c5b` rename_and_add_scraping | 06-15 | `source_registry` table এর নাম `verified_sources` করা, scraping এর selector column যোগ |
| `a1b2c3d4e5f6` add_multimodal_predictions | 06-23 | পুরোনো `multimodal_predictions` table |
| `3e7f64e4c47d` add_missing_tables | 07-06 | users, refresh/reset token, expert review, notification ইত্যাদি |
| `f89542b9b55a` | 07-06 | `query_type_enum` এ `site_restricted` |
| `seed_admin_user_001` | 07-07 | default admin account তৈরি (hardcoded email ও hash) |
| `be6f76179d91` | 07-07 | `search_provider_enum` এ `internal_site` |
| `140d46863ca2` add_source_fields | 07-28 | `verified_sources` এ `display_name_en`, `search_language`, `js_rendered` |
| `9624a66f7531` add_pdf_schema_tables | 08-06 | thesis এর DatabaseDescription.pdf অনুযায়ী নতুন table (`submissions`, `_v2` table, tier, profile ইত্যাদি), শুধু যোগ করা হয়েছে, কিছু মোছা হয়নি |
| `9ed4fe39e0e9` cutover_backfill | 08-06 | পুরোনো data নতুন table এ কপি (primary key একই রাখা হয়েছে, যাতে পুরোনো link কাজ করে) এবং default credibility tier seed করা |
| `b3f1c9a2d4e7` add_3d_verdict_model | 09-30 | একক TRUE/FALSE verdict এর বদলে Source/Content/Date এর তিন মাত্রার model |
| `c4a2d8f1e9b3` structured_expert_votes | 10-01 | expert vote কে ঐ তিন মাত্রায় ভাগ করা |
| `d7e3b5f0a1c6` overall_verdict_and_voting_config | 10-01 | Overall verdict এর enum ও `voting_config` table |
| `e2f4c7a9b3d1` voting_engine_foundations | 10-01 | `final_*` column, `finalized_at`, voting engine এর ভিত্তি |
| `f8a1d3c5e7b2` no_automated_overall_verdict | 10-01 | নিয়ম কার্যকর করা: automated system overall verdict দেবে না |
| `a3c6e9f1b4d8` add_incomplete_check_state | 10-01 | status এর enum এ `INCOMPLETE` যোগ |
| `b7d2e4f6a8c1` manipulation_flags | 10-01 | `manipulation_flags` column (পরে মুছে ফেলা হয়েছে) |
| `c9e1f3a5b7d4` photocard_extraction_provenance | 10-02 | photo card extraction এর উৎস (provenance) এর column |
| `d1a7c3e5f9b2` scope_aware_results_and_jobs | 10-02 | `claim_scope`, `pipeline_version`, `analysis_details` এবং `verification_jobs` table |
| `a6d9e2f4b8c0` retire_legacy_schema | 10-03 | পুরোনো table মুছে ফেলা এবং `_v2` table এর নাম ঠিক করা |
| `b2f8a4d6c9e1` personal_result_delivery | 10-04 | `result_deliveries` table; expert এর credibility প্রথমে হিসাব না করে রাখা |
| `c7e2a9d4f1b3` headline_alteration_and_body_scores | 10-05 | Headline Alteration ও body score এর column। পুরোনো logic এ তৈরি সব submission মুছে ফেলা হয়। |
| `d4b8e1f7a2c5` overall_vote_escalation_and_status_labels | 10-06 | `is_admin_decision`, `escalated_at`, `max_review_votes/hours`; `max_tier_weight` মুছে ফেলা |
| `e5c9a3f7b1d2` photocard_extractions | 10-06 | `ocr_extractions` table এর নাম `photocard_extractions` করা (শুধু Gemini ব্যবহার হয়) |
| `f3b7d1e9a2c4` drop_unused_user_fields | 10-07 | users এর অব্যবহৃত column ও `user_profiles` table মুছে ফেলা (**এটিই বর্তমান head**) |

---

## 7. `app/shared/`

| File | কাজ |
|---|---|
| `base_model.py` | `Base` (DeclarativeBase) এবং কয়েকটি mixin: `UUIDMixin` (UUID primary key, Python এ তৈরি হয়), `TimestampMixin` (`created_at`/`updated_at` এর server default ও onupdate), `ReprMixin`। |
| `base_repository.py` | Generic `BaseRepository[ModelT]`: `get_by_id` (না পেলে `RecordNotFoundError`), `get_by_id_or_none`, `list_all`, `count`, `create`/`bulk_create` (flush ও refresh করে; `IntegrityError` হলে rollback করে `DuplicateRecordError` দেয়), `update(**fields)`, `delete`, `delete_by_id`। প্রায় সব repository এটি extend করে। |
| `dependencies.py` | FastAPI এর DI wiring: request প্রতি একটি session (শেষে commit), repository factory, `app.state` থেকে singleton service বের করা (cache, embedding, NER, NLI, http client), পুরো `VerificationService` তৈরি করা, `SourceService`। |
| `models_registry.py` | সব ORM model একটি জায়গা থেকে import করে, যাতে SQLAlchemy এর mapper registry সম্পূর্ণ থাকে। `main.py` ও Alembic এর `env.py` এটি ব্যবহার করে। |
| `status_labels.py` | Backend এর enum কে user এর দেখার মতো লেখায় রূপান্তর ("Found"/"Not Found", "Exact Matched"/"Meaning Preserved"/"Altered", "Likely Fake"/"Likely Real" ইত্যাদি)। frontend এর `status-labels.ts` ও extension এর `shared.js` এ একই তালিকা আছে। `ai_decision_label()` multimodal এর prediction কে লেখায় রূপান্তর করে। |
| `email_service.py` | SMTP wrapper। `send_otp_email`: SMTP configure না থাকলে OTP console এ log করে, ব্যর্থ হলে `EmailDeliveryError` দেয়। `send_result_email`: চূড়ান্ত রায় ও result page এর link পাঠায়। blocking smtplib এর call `asyncio.to_thread` এ চলে। Gmail app password এর মাঝের space নিজে থেকেই বাদ দেয়। |

### `app/shared/utils/`

| File | কাজ |
|---|---|
| `article_url_heuristics.py` | URL দেখে বোঝার চেষ্টা করে এটি কোনো article এর URL কিনা। প্রথমে নিশ্চিতভাবে article নয় এমন URL বাদ দেয় (tag, feed, search, epaper), তারপর source এর নিজস্ব `article_url_patterns` মেলায়। কোনোটা না মিললে URL এর গঠন দেখে বিচার করে (`/YYYY/MM/DD/`, সংখ্যার ID, hash এর মতো slug)। এতে কোনো সাইট URL এর ধরন বদলালেও সব candidate একসাথে বাদ পড়ে যায় না। |
| `bangla_normalizer.py` | বাংলা text normalize করা: NFC, zero-width character বাদ, punctuation map (`।` থেকে `.`, curly quote থেকে সাধারণ quote), বাংলা থেকে ASCII digit, whitespace এক করা। `normalize_source_name()` static alias map ব্যবহার করে source এর নাম থেকে domain বের করে। `extract_canonical_domain()` URL বা domain থেকে `www.` ছাড়া host বের করে। |
| `dates.py` | `parse_publication()` ISO বা লেখা আকারের তারিখ (বাংলা digit ও বাংলা মাসের নাম সহ) parse করে, এবং সময়কে **Asia/Dhaka** এর তারিখে রূপান্তর করে। offset না থাকলে Dhaka ধরে নেয় এবং `tz_assumed` চিহ্ন দেয়। `ParsedPublication` dataclass এ ফলাফল থাকে। |
| `domains.py` | কোন host দাবিকৃত source এর অনুমোদিত domain, তা যাচাই করে। `allowed_domains_for()` canonical domain ও সংশ্লিষ্ট অন্য channel একত্র করে, `is_allowed_host()` subdomain সহ মেলায়। S04 ও S05 এ redirect বা অন্য domain এর জিনিস আটকাতে ব্যবহার হয়। |
| `hashing.py` | Identity hash তৈরি। `compute_claim_hash()` claim এর **একমাত্র** identity function: normalized headline, body (scope এ body থাকলে তবেই), canonical source, তারিখ, scope ও pipeline version, sorted-key JSON থেকে SHA-256 করা। এছাড়া আছে `compute_url_hash` (tracking parameter বাদ দিয়ে), `compute_text_hash`, `compute_search_query_hash` (provider, query ও তারিখ নিয়ে)। |
| `headline_preview.py` | Notification এর জন্য শিরোনামের প্রথম ৫টি শব্দ, বেশি থাকলে শেষে "..."। |
| `keyword_extractor.py` | YAKE দিয়ে keyword বের করা (extractor `lru_cache` এ রাখা)। ব্যর্থ হলে stopword বাদ দিয়ে শব্দের frequency দেখে keyword বেছে নেয়। `extract_headline_keywords()` S03 এর search query ও S07 এর ranking এ ব্যবহার হয়। `compute_keyword_overlap()` হলো Jaccard। |
| `text_cleaner.py` | Extract করা body থেকে HTML, boilerplate ("আরও পড়ুন", share/copyright) ও metadata লাইন বাদ দেয়। `clean_title()`, এবং `truncate_for_nli()` (বাক্যের শেষ দেখে কাটে, এটি embedding এও ব্যবহার হয়)। |

---

## 8. Feature package (`app/features/`)

প্রতিটি feature folder এর `__init__.py` খালি (কিছু file এ UTF-8 BOM আছে)।

### 8.1 `auth/`: account, login, token

| File | কাজ |
|---|---|
| `models.py` | `User` (email unique, bcrypt hash, `role` (user/expert/admin) এর CHECK constraint, `is_active`, `total_submissions` counter), `RefreshToken` (শুধু SHA-256 hash রাখা হয়, `revoked`, `expires_at`), `PasswordResetToken` (OTP এর hash, `used`)। |
| `schemas.py` | Register, login, refresh, password reset ও change এর request। `TokenResponse`, `UserMeResponse` (register এর response এ token ও যোগ করা হয়)। |
| `repository.py` | `UserRepository` (email দিয়ে খোঁজা, role অনুযায়ী তালিকা ও গণনা), `RefreshTokenRepository` (raw token দিয়ে বৈধ token খোঁজা `FOR UPDATE` lock সহ, revoke, user এর সব token revoke), `PasswordResetTokenRepository` (বৈধ OTP খোঁজা, একই hash আগে ব্যবহার হয়েছে কিনা)। |
| `security.py` | bcrypt দিয়ে hash ও যাচাই (password ৭২ byte এ কাটা হয়), HS256 JWT access token তৈরি ও decode (expire হলে বা invalid হলে আলাদা error), refresh token (`token_urlsafe(64)`, শুধু hash রাখা হয়)। FastAPI dependency: `get_current_user` (Bearer token নিয়ে DB থেকে user লোড করে, inactive হলে 403), `get_current_user_optional` (token না থাকলে বা ভুল হলে None দেয়), `require_role(*roles)`। |
| `service.py` | `AuthService`: register (password এর শক্তি যাচাই: ৮ অক্ষর, একটি সংখ্যা, একটি বড় হাতের অক্ষর; email আগে থেকে আছে কিনা), login (ভুল credential হলে একই error), refresh (**rotation**: পুরোনো token সাথে সাথে বাতিল না করে একটি grace window পর্যন্ত বৈধ রাখে, যাতে network এ response হারালে user logout না হয়ে যান), logout, password reset (সংখ্যার OTP, collision হলে আবার তৈরি করে, email এ পাঠায়), confirm ও change (দুটোতেই user এর সব refresh token revoke হয়)। |
| `router.py` | `/auth/register`, `/login`, `/refresh`, `/logout`, `/me`, `/password-reset/request`, `/password-reset/confirm`, `/change-password`। |

### 8.2 `users/`: নিজের profile ও submission

| File | কাজ |
|---|---|
| `schemas.py` | `SubmissionSummary`, `SubmissionStatsResponse`, `ProfileResponse`, `UpdateProfileRequest`। |
| `service.py` | `UserAccountService`: নিজের submission এর তালিকা (প্রতিটি সম্পর্কিত table এর জন্য পুরো page এ একটি করে query, `rows_by_submission`), গণনা ও নাম বদলানো; `to_profile_response()`। |
| `router.py` | পাতলা router, কাজ service এ। `GET /users/me/submissions`: নিজের সব submission (PENDING/FAILED সহ), প্রতিটির preliminary ফলাফল, headline status, expert এর চূড়ান্ত রায় (reuse করা copy হলে মূল submission থেকে), photo card এর ছবির URL। `GET /users/me/submissions/stats`: গণনা। `GET/PUT /users/me/profile`: expert রা নিজের profile বদলাতে পারেন না (403)। |

### 8.3 `admin/`

| File | কাজ |
|---|---|
| `schemas.py` | Expert এর CRUD, platform stats, credibility tier, voting config এর request ও response, এবং admin home dashboard এর model (`DashboardClaim`, `DashboardExpert`, `DashboardActivity`, `AdminDashboardResponse`)। |
| `service.py` | `AdminService`: expert account তৈরি (সাথে `ExpertProfile`), তালিকা, update, password reset (token revoke সহ), activate/deactivate। platform stats। credibility tier এর CRUD, যার validation বলে active tier গুলো মিলে **0–100% পুরোটা ঢাকতে হবে, ফাঁক বা overlap রাখা যাবে না**। voting config পড়া ও update; activation threshold বদলালে সব expert এর credibility আবার হিসাব হয়। |
| `dashboard.py` | Admin home page এর data এক call এ: escalated, review এ থাকা, processing ও failed এর গণনা; সবচেয়ে পুরোনো review, সাম্প্রতিক submission ও সিদ্ধান্ত; expert দের শেষ vote; সাম্প্রতিক কার্যক্রম। |
| `router.py` | `/admin/experts...`, `/admin/stats`, `/admin/dashboard`, `/admin/credibility-tiers...`, `/admin/voting-config` (সবই শুধু admin এর জন্য)। |

### 8.4 `sources/`: যাচাইকৃত সংবাদমাধ্যম

| File | কাজ |
|---|---|
| `models.py` | `VerifiedSource`: `canonical_name` (domain, unique), নাম (বাংলা ও ইংরেজি), `aliases` (JSONB, GIN index), `base_url`, `rss_url`, ভাষা, `is_active`, এবং scraping এর configuration: `body_selectors`, `title_selectors`, `date_selectors`, `internal_search_url` (`{query}` template), `article_url_patterns` (regex)। |
| `schemas.py` | তৈরি করা (domain ও ভাষা যাচাই, alias এর duplicate বাদ, base_url ঠিক করা), partial update (`extra=forbid`), response, ও page আকারে তালিকা। |
| `repository.py` | canonical name দিয়ে খোঁজা, alias দিয়ে খোঁজা (JSONB `@>`, শুধু active), `resolve_source()` (প্রথমে canonical, তারপর alias), active বা সব source এর তালিকা ও গণনা। |
| `service.py` | `SourceService`: CRUD ও page আকারে তালিকা। |
| `resolution.py` | `resolve_claimed_source()`: user যে source এর নাম লিখেছেন তা থেকে canonical domain বের করার **একমাত্র** জায়গা। ক্রম: (১) URL বা domain, (২) static alias map, (৩) DB। কিছু না মিললে None। verification ও photo card service এবং S01 সবাই এটি ব্যবহার করে, যাতে source অজানা থাকলে পুরো internet এ খোঁজা শুরু না হয়। |
| `router.py` | `GET /sources` (public; ড্রপডাউনে শুধু active source), POST/PUT/DELETE (শুধু admin)। |

### 8.5 `submissions/`

| File | কাজ |
|---|---|
| `models.py` | `Submission` (type, headline, body, দাবিকৃত source এর text ও id, তারিখ, submitter, `content_hash` (identity), `duplicate_of_submission_id` (reuse হলে মূল submission), `status`, `processing_phase`, `failure_reason`, `escalated_at`)। এই file এ আরও আছে `SourceEvidenceQuery` (S04 এ চালানো query এর log), `RetrievedArticle` (যে article গুলো evidence হিসেবে পাওয়া গেছে, `(submission_id, url_hash)` unique, `rank_score`), `PhotocardExtraction` (ছবির key, Gemini এর status, failure code, model, কতবার চেষ্টা, `extraction_details` JSONB)। |
| `repository.py` | `SubmissionRepository`: row lock সহ load (vote এর race condition আটকাতে), reuse এর জন্য candidate (একই hash, verified, duplicate নয়), চলমান claim খোঁজা, status ও phase এর transition (`mark_processing`, `mark_ai_done`, `mark_failed`, যা শুধু প্রথমবার FAILED হলেই True দেয়; `escalate_if_open`, যা শর্তসাপেক্ষে update করে), Fact Explorer এর search (keyword, status, overall verdict, method, তারিখ, source, review state; MULTIMODAL ও structured দুই ধরনের verdict CASE দিয়ে মেলানো), `explorer_summary()`। এছাড়া `RetrievedArticleRepository`, `PhotocardExtractionRepository` । |
| `schemas.py` | `SubmissionLookupResponse`: কোন detail endpoint call করতে হবে তা জানার জন্য type ও মৌলিক তথ্য। |
| `access.py` | `viewer_can_see()`: যে submission এর ফলাফল প্রকাশিত (EXPERT_REVIEW/FINALIZED/ESCALATED), সেটি সবাই দেখতে পারে। PENDING বা FAILED submission শুধু মালিক, expert ও admin দেখতে পারেন। anonymous submission তার ID দিয়ে দেখা যায়। |
| `router.py` | `GET /submissions/{id}` (type ও status), `GET /submissions/{id}/voting-details` (চূড়ান্ত হওয়ার পরেই কেবল reviewer দের vote ও যুক্তি দেখায়, তার আগে 404)। |

### 8.6 `verification/`: text verification এর মূল অংশ

| File | কাজ |
|---|---|
| `models.py` | `VerificationResult`: AI এর নিজের ফলাফল, যা একবার লেখার পর আর বদলায় না (`source_status`, `content_status`, `headline_check_status`, `headline_exact_match`, `body_comparison_status`, `date_status`, `confidence`, `reasoning`, `top_article_id`, তিনটি correspondence measurement, `claim_scope`, `pipeline_version`, `analysis_details` JSONB, `reused_from_submission_id`)। expert এর দেওয়া মান: `overall_verdict`, `finalized_at`। কিছু legacy column ও আছে। `VerificationJob`: background job এর DB queue (kind, status, attempts/max, `locked_at`/`locked_by` heartbeat, `payload`)। |
| `schemas.py` | Pipeline এর output ও API এর model: `MetricDetail`, `SearchAccounting`, `DateAnalysis`, `HeadlineDifference`, `HeadlineSemanticAssessment`, `HeadlineAlterationDetail`, `BodySimilarityMetric`/`Report`, `ExecutionTimings`, `AnalysisDetails` (`analysis_details` JSONB এর গঠন), `VerificationRequest` (whitespace বাদ দেওয়া ও validation), `VerificationResponse`, `VerificationQueuedResponse`, `VerificationStatusResponse`। `NLIScoresSchema` NLI service এর output। |
| `repository.py` | `ResultRepository`: submission দিয়ে result খোঁজা, `upsert_result()` (শুধু automated column লেখে, expert এর column কখনো ছোঁয় না), `record_timings()` (`analysis_details.timings` ও মোট সময়)। |
| `job_repository.py` | `VerificationJobRepository`: `enqueue` (submission প্রতি একটি job, আবার call করলেও নতুন job হয় না), `claim_next` (`FOR UPDATE SKIP LOCKED`; heartbeat পুরোনো হয়ে গেলে RUNNING job আবার তুলে নেয়; kind অনুযায়ী আলাদা lane), `heartbeat`, `mark_done`, `release_or_fail` (permanent error হলে বা চেষ্টা শেষ হলে FAILED, নাহলে আবার QUEUED)। |
| `jobs.py` | `JobDeps` (`app.state` থেকে নেওয়া dependency), `execute_job()` (নিজস্ব session খুলে `_HANDLERS` registry থেকে kind অনুযায়ী handler চালায়: `_run_multimodal`, `_run_photocard`, বাকি সব `_run_source_based`; submission আগেই প্রক্রিয়া হয়ে থাকলে কিছু করে না, commit/rollback ও error mapping এক জায়গায়)। `VerificationJobWorker` দুটি **lane** এ চলে: "general" (text ও multimodal) আর "photocard" (Gemini এর retry এর জন্য অপেক্ষা যেন অন্য কাজ আটকে না রাখে)। প্রতিটি lane এ আছে semaphore দিয়ে concurrency এর সীমা, `wake()` event, heartbeat task, এবং শেষ পর্যন্ত ব্যর্থ হলে submission FAILED করে একবার notification। |
| `service.py` | `VerificationService`: `verify()` (source resolve, context তৈরি, orchestrator চালানো, reuse হলে requester এর নিজের submission এ ফলাফল copy, timing রেকর্ড, response), `run_for_submission()` (job থেকে চালানোর entry), `register_claim()` (async এ গ্রহণ: reuse, চলমান claim, অথবা নতুন job), `get_result()`। |
| `reuse.py` | `result_is_reusable()`: কোন ফলাফল আবার ব্যবহার করা যাবে তার নিয়ম। pipeline version একই হতে হবে, নিজে copy হওয়া চলবে না, INCOMPLETE থাকা চলবে না, source CONFIRMED হলে headline verdict থাকতে হবে, এবং body score UNAVAILABLE হওয়া চলবে না। `ResultReuseService`: `find_reusable()`, এবং `materialize()` (ফলাফল target submission এ copy করে, timing বাদ দিয়ে, `duplicate_of` ও EXPERT_REVIEW set করে)। expert এর ফলাফল copy হয় না, প্রদর্শনের সময় মূল submission থেকে পড়া হয়। |
| `presenter.py` | DB থেকে `VerificationResponse` তৈরির **একমাত্র** পথ: `resolve_scope`, `effective_expert_row` (copy হলে মূল submission এর expert ফলাফল), `effective_status`, `is_headline_result` (পুরোনো row আলাদা করা), `parse_analysis` (JSON এর যে অংশ পুরোনো আকারে আছে শুধু সেটুকু বাদ দেয়), `load_verification_response` (সর্বোচ্চ ৩টি article, S08 যেটি বেছেছে সেটি প্রথমে)। |
| `headline_status.py` | সংরক্ষিত MATCHED কে আরও ভাগ করে দেখায়: হুবহু মিল থাকলে EXACT_MATCHED, নাহলে MEANING_PRESERVED। কোনো তুলনা নতুন করে চালায় না। প্রমাণ এই ক্রমে দেখে: `headline_exact_match` column, `basis=="exact"`, তারপর সংরক্ষিত headline আর title আবার মিলিয়ে দেখা। |
| `verdict_compat.py` | `format_verdict_display()`: expert queue এর "AI said" কলামের জন্য এক লাইনের সারাংশ। |
| `router.py` | `POST /verify` (sync), `POST /verify/async`, `GET /verify/{id}`, `GET /verify/{id}/status`। |
| `pipeline/` | Section 9 দেখুন। |
| `analysis/` | Section 9.3 দেখুন। |

### 8.7 `photocard/`

| File | কাজ |
|---|---|
| `router.py` | `POST /photocard/verify/async`: ছবির ধরন (jpeg/png/gif/webp) ও আকার (≤১০ MB) যাচাই, তারপর গ্রহণ ও 202। `GET /photocard/{id}`: যেকোনো অবস্থার report। |
| `dependencies.py` | `PhotoCardService` এর DI wiring, storage `app.state` থেকে নেওয়া। |
| `schemas.py` | `PhotoCardAcceptedResponse` (202 এর উত্তর), `PhotoCardResultResponse` (headline, source এর id ও নাম, ছাপা তারিখ, extraction এর status, কতবার চেষ্টা, model, ব্যর্থতার কারণ, ছবির URL, verification)। |
| `service.py` | `PhotoCardService`: `accept_upload` (ছবি, submission, extraction row ও job একটি transaction এ; ছবি রাখা না গেলে 503), `process_submission` (job এর মূল কাজ: phase বদল, ছবি download, Gemini দিয়ে extraction, ব্যর্থ হলে `PermanentJobError`; সফল হলে submission এ headline/source/date বসানো, photo card এর hash, pipeline চালানো, reuse হলে copy ও notification, timing; crash এর পর retry হলে Gemini আবার call করে না), `get_result`। `extraction_failures()` attempt এর outcome কে user এর পড়ার মতো লেখায় রূপান্তর করে। |
| `claim_extraction.py` | `PhotocardClaimExtractor.extract()`: active source এর তালিকা (alias সহ) Gemini কে দেয়। ফলাফল তিন রকম হতে পারে: **API_FAILED** (সব request ব্যর্থ), **INVALID_CONTENT** (headline নেই, অথবা active source চেনা যায়নি; retry হয় না), **SUCCEEDED**। headline কমপক্ষে ৮ অক্ষর ও অন্তত একটি অক্ষর থাকতে হবে। source এখনো active আছে কিনা আবার যাচাই করে। তারিখ parse না হলে তারিখ ছাড়াই চলে (ব্যর্থ হয় না)। `CardExtraction` dataclass ও user কে দেখানোর message এখানে। |
| `gemini_prompt.py` | Gemini কে যা পাঠানো হয় ও যা ফেরত আসে: `SourceOption`, `FieldStatus`/`SourceStatus`, `GeminiPhotocardFields`, `SYSTEM_INSTRUCTION`, `build_user_prompt()`, `build_response_schema()`। |
| `gemini_key_pool.py` | `GeminiKeyPool` (process জুড়ে key rotation), `limit_info()` (429 থেকে দৈনিক নাকি মিনিটের সীমা), `key_pool()`, `reset_key_pools()`। |
| `gemini_image_extractor.py` | `extract_with_gemini()` (বাইরের API, আগের মতোই) ও request এর loop: system instruction (ছবির ভেতরের লেখা নির্দেশ হিসেবে মানা যাবে না, headline হুবহু তুলে দিতে হবে, শুধু তালিকার source থেকে বাছতে হবে), structured `responseSchema` (source এর মান enum দিয়ে সীমাবদ্ধ), `GeminiPhotocardFields` দিয়ে validation। **batch এ retry:** প্রতি batch এ সর্বোচ্চ ৩টি request, batch এর পর ১০ সেকেন্ড বিরতি, সর্বোচ্চ ৩টি batch। 400/401/403/404 হলে সাথে সাথে থামে। **Key pool:** কোনো key এর quota (429) শেষ হলে সেটি সরিয়ে রেখে পরের key দিয়ে request পাঠায়, এবং এই তথ্য পুরো process এ share হয়। key কখনো log এ যায় না, শুধু তার ক্রমিক নম্বর। MIME type বের করা, প্রতিটি attempt এর হিসাব (`GeminiAttempt`)। |
| `card_date.py` | ছবিতে ছাপা তারিখ parse করে, কিছু অনুমান না করে। দিন, মাস ও বছর তিনটিই থাকতে হবে। বাংলা ও ইংরেজি মাস, বাংলা ordinal (১লা, ২১শে), সংখ্যায় লেখা d/m/y বা y-m-d বোঝে। দুটি আলাদা তারিখ পেলে বা অস্পষ্ট হলে None দেয়। |
| `verification_stages.py` | `compute_photocard_hash()`: photo card এর identity, যার version এ pipeline version, headline comparison method ও model এর নাম থাকে। `PhotocardNormalizerStage`: S01 এর subclass, body থাকলে error দেয় এবং photo card এর নিজস্ব hash বসায়। `build_photocard_stages()`: shared stage তালিকায় S01 বদলে দেয়। |
| `storage_service.py` | `PhotoCardStorageService`: MinIO তে `photocard/{submission_id}/{নিরাপদ নাম}`। upload ও download ব্যর্থ হলে exception না দিয়ে False/None দেয়। ৪টি thread এর আলাদা pool, এবং presigned URL। |

### 8.8 `multimodal/`

| File | কাজ |
|---|---|
| `models.py` | `MultimodalAnalysis` (submission এর সাথে ১:১): ছবির key, prediction (FAKE/NON_FAKE), দুটি confidence, তিনটি embedding (text ৭৬৮, ছবি ১৭৯২, দুটো মিলিয়ে ২৫৬০; Postgres ARRAY), `model_version`, `is_duplicate_of_id`, এবং expert এর `expert_overall_verdict`, `finalized_at`। |
| `schemas.py` | `MultimodalPredictionResponse`, `MultimodalPredictionDetail`, `PredictionListResponse`। |
| `repository.py` | `MultimodalAnalysisRepository` (BaseRepository extend করে না): create (numpy থেকে list), id বা submission দিয়ে খোঁজা, update, সাম্প্রতিক তালিকা, duplicate খোঁজার জন্য candidate (একই model version এর সাম্প্রতিক N টি)। |
| `service.py` | `MultimodalPredictionService`: `predict()` (embedding, duplicate খোঁজা, যেখানে তিনটি cosine এর প্রতিটি নিজের threshold পার হতে হবে; duplicate পেলে আগের prediction copy, নাহলে নতুন inference; ছবি upload), `accept_upload()` (async এ গ্রহণ, ব্যর্থ হলে ছবি মুছে দেয়), `process_queued()` (job এর কাজ; আগেই analysis থাকলে আবার করে না; EXPERT_REVIEW ও notification), `users.total_submissions` বাড়ানো। |
| `storage_service.py` | `MultimodalStorageService`: MinIO তে `multimodal/{sid}/{name}`। ব্যর্থ হলে `MultimodalStorageError` (502)। read, delete ও presigned URL। |
| `router.py` | `POST /multimodal/predict/async` (frontend ও extension এটি ব্যবহার করে), `POST /multimodal/predict` (sync), `GET /multimodal/predict/{id}`, `GET /multimodal/by-submission/{id}`, `GET /multimodal/predictions`। |
| `pipeline/model_architecture.py` | Training এর সময়ের architecture: `EfficientNetBackbone` (timm, global avg pool), `BanglaBERTBackbone` (`[CLS]` vector), `MultiFusionFake` (দুটো concat করে LayerNorm, তারপর 1024, 512, 2 আকারের MLP, GELU ও dropout সহ)। |
| `pipeline/model_loader.py` | `MultimodalModelLoader`: `img_backbone.pt`, `text_backbone.pt`, `classifier.pt` ও `tokenizer/` আছে কিনা দেখে, thread এ `torch.load(weights_only=True)` দিয়ে load করে, eval mode এ রাখে। load না হলে property গুলো `ModelNotLoadedError` দেয়। |
| `pipeline/embedding_extractor.py` | text ও ছবির embedding আলাদা thread pool এ একসাথে বের করে; দুটো মিলিয়ে L2-normalized combined vector; `cosine_similarity` ও `is_duplicate()` (তিনটি threshold)। ছবি decode না হলে কালো ছবি ধরে নেয়। |
| `pipeline/inference_engine.py` | `MultimodalInferenceEngine.predict()`: tokenize, transform, তারপর backbone ও classifier, softmax, `PredictionResult` (label `{0: NON_FAKE, 1: FAKE}`)। |
| `pipeline/__init__.py` | তিনটি class re-export করে। |
| `multimodal_model/` | Training এর `config.json`, tokenizer file, এবং weight (`classifier.pt` git এ আছে; বাকি দুটি local)। |

### 8.9 `expert_review/`

| File | কাজ |
|---|---|
| `models.py` | `ExpertProfile` (`total_votes`, `correct_votes`, `credibility_score`, যা activation threshold এর আগে NULL থাকে), `CredibilityWeightTier` (accuracy% এর পরিসীমা অনুযায়ী vote এর weight), `ExpertReview` (vote এর সময় AI এর ফলাফলের snapshot, expert এর overall ও অতিরিক্ত source/content/date মতামত, যুক্তি, ব্যবহৃত weight ও tier, status, `is_admin_decision`), `VotingConfig` (এক row এর table: M, N, T, margin, সর্বোচ্চ vote ও ঘণ্টা)। model এর docstring এ পুরো নিয়ম লেখা আছে। |
| `schemas.py` | Vote ও edit এর request (যুক্তি অন্তত ৫০ অক্ষর; source CONFIRMED না হলে content ও date দেওয়া যাবে না), review, queue item (AI এর ফলাফল, headline detail, body score, top article, ছবি, `can_vote`, `decision_mode`), history, stats, credibility। |
| `repository.py` | Profile এর get_or_create, active tier ও accuracy অনুযায়ী tier বের করা, review এর query (submission ও reviewer দিয়ে, submission এর সব, গণনা, history যেখানে খোঁজার শব্দ escape করা হয়), voting config এর get_or_create। |
| `service.py` | `ExpertReviewService`: queue তৈরি (expert: যে claim এ এখনো vote দেননি এবং নিজে জমা দেননি; admin: escalated আগে, তারপর বাকি claim শুধু দেখার জন্য), queue item, `submit_vote` (row lock; escalated claim এ expert vote দিতে পারবেন না; নিজের claim বা দ্বিতীয়বার vote চলবে না; AI এর snapshot; tier থেকে weight), admin এর সিদ্ধান্ত, vote edit (শুধু review চলাকালীন), history, stats। মূল নিয়ম: `_tally`/`_evaluate` (weighted vote এ একক নেতা থাকতে হবে, নেতা ≥ T, ভোটার ≥ M, নেতা আর দ্বিতীয়ের ব্যবধান ≥ margin; সমান হলে কখনো চূড়ান্ত হয় না), `review_limits_exceeded` (কোনো একটি সীমা পার হলেই), `_apply_final_decision`, `_update_expert_profiles` (overall verdict সঠিক ছিল কিনা দেখে accuracy update)। |
| `escalation.py` | `notify_admins_of_escalation` (প্রতিটি active admin কে একবার notification), `sweep_review_limits` (সময় বা vote এর সীমা পার হওয়া claim খুঁজে আবার যাচাই করা), `EscalationWorker` (প্রতি ৬০ সেকেন্ডে)। |
| `overall_verdict.py` | Multimodal এর prediction থেকে overall verdict: FAKE হলে FAKE, নাহলে REAL। |
| `public_votes.py` | `PublicVote`/`PublicVotingDetails` schema, এবং `load_public_voting_details()`: চূড়ান্ত হওয়ার পর reviewer দের নাম (নাম না থাকলে "Expert reviewer n"), vote, যুক্তি, এবং সিদ্ধান্ত expert দের ঐকমত্যে নাকি admin এর। copy হলে মূল submission থেকে পড়ে। |
| `router.py` | `/expert/queue`, `/expert/queue/{id}`, `/expert/queue/{id}/vote`, `PUT /expert/reviews/{id}`, `/expert/history`, `/expert/stats`, `/expert/credibility`। |

### 8.10 `notifications/`

| File | কাজ |
|---|---|
| `models.py` | `Notification` (user, title, body, type, link, `is_read`), `ResultDelivery` (`(submission, stage)` primary key; email এর status, কতবার চেষ্টা, পরের চেষ্টার সময়)। |
| `service.py` | `notify_once()`: একই `(user, type, link)` দিয়ে একবারই notification তৈরি করে, SAVEPOINT এর ভেতরে, যাতে notification ব্যর্থ হলেও ফলাফল সংরক্ষণ বাতিল না হয়। `VERIFICATION_COMPLETE` এর লেখা সবসময় একই রকম। preliminary ও final notification এর লেখাও এখানে। |
| `delivery.py` | `reconcile()`: commit হয়ে যাওয়া ফলাফল থেকে "preliminary" ও "final" notification তৈরি করে (sync, async ও reuse তিন ধরনের ক্ষেত্রেই কাজ করে; `SKIP LOCKED`)। `deliver_email()`: row lock নিয়ে ফলাফলের email পাঠায়, ব্যর্থ হলে exponential backoff (সর্বোচ্চ ১ ঘণ্টা)। `ResultDeliveryWorker`: প্রতি ১৫ সেকেন্ডে। |
| `schemas.py` / `repository.py` | `NotificationResponse`, `UnreadCountResponse`; `NotificationRepository` (তালিকা, না-পড়ার সংখ্যা, একটি বা সব পড়া)। |
| `router.py` | পাতলা router: তালিকা, না-পড়া notification এর সংখ্যা, একটিকে বা সবগুলোকে পড়া হিসেবে চিহ্নিত করা। |

### 8.11 `dashboard/`

| File | কাজ |
|---|---|
| `schemas.py` / `service.py` | Response schema; `DashboardService` (stats দুটি conditional-aggregate query তে, top sources, explorer এ batched query)। |
| `router.py` | পাতলা router। `GET /dashboard/stats` (public গণনা), `GET /dashboard/top-sources`, `GET /dashboard/explorer`: Fact Explorer, যেখানে filter দিয়ে খোঁজা যায় এবং প্রতিটি item এ preliminary ফলাফল, চূড়ান্ত রায় ও thumbnail থাকে, সাথে archive এর সারাংশ। |

### 8.12 বাকি feature package

| Path | কাজ |
|---|---|
| `health/router.py` | `GET /health` (app চলছে কিনা, liveness), `GET /health/ready` (DB ও Redis পরীক্ষা, সমস্যা হলে 503)। |
| `cache/cache_service.py` | Redis wrapper: claim pointer (`bgf:claim:{hash}`, TTL সহ), search ফলাফল (`bgf:search:{provider}:{hash}`), কাঁচা key ও value, health check। প্রতিটি method নিজের error নিজে সামলায়, ফলে Redis বন্ধ থাকলেও pipeline চলে (cache ছাড়া)। |
| `nlp/model_identity.py` | Embedding model এর নাম থেকে runtime model, পুরোনো hash এর সাথে মিল রাখা identity tag ও cache prefix। LaBSE এর জন্য সব আগের মতো; অন্য model দিলে hash ও cache আলাদা হয়, তাই model বদল লুকানো থাকে না। |
| `nlp/embedding_service.py` | LaBSE (`sentence-transformers/LaBSE`)। load (thread এ), `encode` (Redis cache সহ), `encode_batch`, `compute_similarity` (normalize করা vector এর dot product, 0–1 এ সীমাবদ্ধ)। model টি class এর মধ্যে রাখা হয়, ফলে সব instance একই model ব্যবহার করে। |
| `nlp/ner_service.py` | BanglaTag NER (HuggingFace pipeline)। load এর পর **audit** চালায়: model এর label এ PER/LOC/ORG আছে কিনা, এবং একটি পরীক্ষামূলক বাক্যে entity খুঁজে পায় কিনা। audit পাস না করলে `usable=False`। লম্বা text বাক্যের chunk এ ভাগ করে tag করে (সর্বোচ্চ ৪০টি chunk)। `NERResult.available` দিয়ে "চালানো যায়নি" আর "কোনো entity পাওয়া যায়নি" আলাদা করা যায়। |
| `nlp/nli_service.py` | mDeBERTa-v3 XNLI এর cross-encoder। label এর নাম entailment/neutral/contradiction কিনা যাচাই করে। `predict(premise, hypothesis)` তিনটি সম্ভাবনা দেয়, অথবা None। শুধু headline ও title এর তুলনায় ব্যবহার হয়। |
| `search/internal_site_client.py` | সংবাদমাধ্যমের নিজের search page (`internal_search_url`) থেকে HTML নিয়ে article এর link বের করে। link এর লেখা ছোট হলে parent heading থেকে title নেয়, একই URL দুইবার এলে লম্বা title টি রাখে। কোনো link এর লেখা query এর সাথে না মিললে পুরো ফলাফল বাদ দেয় (কারণ page টি তখন আসলে JS দিয়ে ভরা হয়, ফলাফল নয়)। ব্যর্থ হলে **exception দেয়**, ফাঁকা তালিকা নয়, যাতে S04 এর হিসাবে "খুঁজে পাওয়া যায়নি" আর "খোঁজা ব্যর্থ" আলাদা থাকে। |
| `search/pygooglenews_client.py` | Google News (bn/BD) এ `site:domain` দিয়ে খোঁজে। দাবিকৃত তারিখ ১৮০ দিনের মধ্যে হলে ±৪৫ দিনের window দেয়। `news.google.com` এর URL কে Playwright দিয়ে আসল সংবাদমাধ্যমের URL এ resolve করে (৪টি একসাথে; Cloudflare এর token বাদ দেয়)। |
| `articles/schemas.py` | Pipeline এর internal DTO: `CandidateArticleSchema` (S04 এর output), `RankedArticleSchema` (S06/S07 এর output; এটি API তে `matched_articles` হিসেবেও যায়), এবং দুটি অব্যবহৃত schema। |

---

## 9. Verification pipeline (S01–S13)

### 9.1 Pipeline এর কাঠামো (`verification/pipeline/`)

| File | কাজ |
|---|---|
| `context.py` | `PipelineContext` (dataclass): একটি verification run এর পুরো অবস্থা। এতে থাকে input, normalize করা মান, `source_config` (dict), `content_hash`, reuse এর তথ্য, search query, প্রতিটি provider call এর হিসাব, fetch ও extraction এর গণনা, candidate/extracted/ranked article, `top_article`, `analysis` (`AnalysisDetails`), চূড়ান্ত status, timing ও error। docstring এ লেখা আছে কোন ফলাফল কোন stage এর দায়িত্ব। এর property: `has_body`, `has_evidence`, `retrieval_failed`, `source_confirmed`, `elapsed_ms`। এছাড়া `PipelineStage` Protocol ও `build_context()` (body দেখে scope ঠিক করে)। |
| `factory.py` | `build_verification_stages()`: ১৩টি stage ও তাদের dependency একসাথে জোড়া লাগানোর একমাত্র জায়গা। |
| `orchestrator.py` | `PipelineOrchestrator.run()`: stage গুলো ক্রমানুসারে চালায়, প্রতিটির timing রাখে। S02 এ reuse পাওয়া গেলে S03–S13 বাদ দেয়। **Critical stage** (S01, S08, S12, S13) ব্যর্থ হলে submission FAILED করে `PipelineError` দেয়। অন্য stage ব্যর্থ হলে error রেকর্ড করে চলতে থাকে, এবং সংশ্লিষ্ট ফলাফল "unavailable/incomplete" দেখায়। docstring এ প্রতিটি stage critical কিনা তার একটি তালিকা আছে। |
| `source_registry.py` | `verified_sources` table এর **reference snapshot** (2026-10-03 এ DB থেকে নেওয়া, inactive source সহ): `SourceConfig` TypedDict, `SOURCE_REGISTRY` (১০টি সংবাদমাধ্যম: alias, selector, search URL, URL pattern), `SOURCE_RECORD_METADATA` (মূল ID ও timestamp)। runtime এ source resolve হয় DB থেকে, এই file থেকে নয়। শুধু `scripts/seed_verified_sources.py` এটি পড়ে। *(এই file এ কোনো পরিবর্তনের প্রস্তাব নেই।)* |

### 9.2 Stage গুলো (`pipeline/stages/`)

| Stage | File | কাজ |
|---|---|---|
| S01 | `s01_normalizer.py` | headline ও body normalize করা (digit বদলায় না)। source resolve করা, না পেলে `NormalizationError` (এটি একটি backstop, আসল যাচাই service এ আগেই হয়ে যায়)। DB থেকে `source_config` তৈরি (selector, search URL, URL pattern, base_url ও alias থেকে `allowed_domains`)। `compute_claim_hash`। |
| S02 | `s02_cache_lookup.py` | Reuse খোঁজা। প্রথমে Redis এর pointer দেখে (version মেলে কিনা, submission এখনো আছে কিনা, ফলাফল reuse করা যায় কিনা; সমস্যা থাকলে pointer মুছে দেয়)। না পেলে DB তে খোঁজে এবং পেলে Redis এ pointer লেখে। reuse পেলে `cache_hit`, `reused_from_submission_id` ও `source_status` set করে। `write_pointer()` NOT_FOUND ফলাফলের জন্য ছোট TTL ব্যবহার করে (S13 ও এটি call করে)। |
| S03 | `s03_query_generator.py` | `site:domain` সহ সর্বোচ্চ ৬টি query: পুরো headline, সব keyword, প্রথম ৩টি ও প্রথম ৪টি keyword, এবং তারিখ থাকলে headline ও keyword এর সাথে তারিখ (`DATE_BOUND`)। user এর লেখা `site:` বাদ দেওয়া হয়। body কখনো search এ ব্যবহার হয় না। |
| S04 | `s04_source_search.py` | প্রতিটি query × provider (internal site, Google News) একসাথে চালায়। cache থেকে ফলাফল নেয় বা cache এ রাখে। প্রতিটি call এর ফলাফল হিসাব করে: SUCCESS, SUCCESS_EMPTY, FAILED, SKIPPED (internal search configure করা নেই), CACHED। এখান থেকে `search_adequate` ঠিক হয়। অনুমোদিত domain এর বাইরের এবং article নয় এমন URL বাদ দেয়, URL canonical করে duplicate বাদ দেয় (internal site কে অগ্রাধিকার দিয়ে)। তারিখ শুধু `DATE_BOUND` query তে ব্যবহার হয়, যাতে ভুল দাবিকৃত তারিখের কারণে আসল article বাদ না পড়ে। |
| S05 | `s05_evidence_retrieval.py` | প্রথম `top_k` টি candidate fetch করে। ধাপ ১: httpx দিয়ে (একসাথে ৮টি, একই domain এ ০.৫ সেকেন্ড বিরতি, browser এর মতো header)। redirect হয়ে অন্য domain এ গেলে বাদ দেয় (`_RedirectRejected`)। 401/403/406/429/503 পেলে বা page এ JS shell বা bot-wall দেখলে ধাপ ২: Playwright Chromium দিয়ে (একসাথে ৪টি, Cloudflare এর জন্য ৩ সেকেন্ড করে ৫ বার অপেক্ষা পর্যন্ত, শুধু audio ও video আটকানো হয়)। Windows এ আলাদা thread ও event loop এ চলে। ফলাফল `context.fetched_html` এ রাখে, এবং fetch এর গণনা রাখে। |
| S06 | `s06_article_extractor.py` | প্রতিটি HTML এর জন্য executor এ: প্রথমে প্রকাশের তারিখ খোঁজে (source এর date selector, JSON-LD `datePublished`, meta tag, `<time itemprop>`; `dateModified` কখনো নয়)। এরপর body/title বের করার ক্রম: source এর selector (কোন selector বারবার ব্যর্থ হচ্ছে তা track করে), JSON-LD `articleBody`, trafilatura, readability, BeautifulSoup heuristic, og:description। title থেকে সংবাদমাধ্যমের নামের অংশ বাদ দেয়। ফলাফল `RankedArticleSchema`। |
| S07 | `s07_evidence_ranker.py` | Score = ০.৫৫ × semantic similarity (headline বনাম title, title না থাকলে body এর শুরু) + ০.২৫ × keyword overlap + ০.২০ × domain bonus। Levenshtein ratio ০.৮৫ এর বেশি হলে +০.১৫, ০.৭০ এর বেশি হলে +০.০৮। দাবিকৃত তারিখ ইচ্ছা করে ranking এ ব্যবহার হয় না। ন্যূনতম score এর নিচে বাদ, সর্বোচ্চ `max_ranked` টি রাখে। ৩টির বেশি থাকলে `CrossEncoderReranker` দিয়ে আবার সাজায়। |
| — | `cross_encoder_reranker.py` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` model, process জুড়ে একটিই instance, thread-safe ভাবে load হয়। prediction thread এ চলে, ব্যর্থ হলে আগের ক্রম রাখে। |
| S08 | `s08_source_correspondence.py` | দাবিকৃত সংবাদমাধ্যম কি **এই নির্দিষ্ট খবরটিই** প্রকাশ করেছে? প্রতিটি ranked article এর জন্য তিনটি measurement: headline বনাম title এর similarity, title এ claim এর keyword কতটা আছে, title ও প্রাসঙ্গিক অনুচ্ছেদে keyword কতটা আছে। `assess_correspondence` এর মাধ্যমে level STRONG, PLAUSIBLE, NONE বা UNKNOWN। প্রথম STRONG (না পেলে প্রথম PLAUSIBLE) article টি `top_article` হয়। `decide_source` থেকে CONFIRMED/NOT_FOUND/INCOMPLETE। search এর হিসাব `analysis.search` এ রাখে। **এটি critical stage।** |
| S09 | `s09_headline_alteration.py` | শুধু headline এর তুলনা, শুধু source এর **title** এর সাথে। NOT_FOUND হলে status SOURCE_NOT_FOUND, অন্যভাবে নিশ্চিত না হলে SOURCE_CHECK_INCOMPLETE, তুলনা ব্যর্থ হলে MODEL_UNAVAILABLE। বাকি ক্ষেত্রে `HeadlineComparator` চালিয়ে `content_status` ও `HeadlineAlterationDetail` তৈরি করে। |
| S10 | `s10_body_similarity.py` | Claim এ body থাকলে এবং source CONFIRMED হলে `compare_bodies` দিয়ে চারটি score। body না থাকলে SKIPPED, তুলনার কিছু না থাকলে UNAVAILABLE। এটি কখনো verdict দেয় না। |
| S11 | `s11_date_verification.py` | Source CONFIRMED হলে দাবিকৃত তারিখ বনাম article এর তারিখ (Asia/Dhaka এর দিন হিসেবে)। দাবিকৃত তারিখ না থাকলে None, article এর তারিখ জানা না থাকলে INCOMPLETE। provenance সহ `DateAnalysis`। |
| S12 | `s12_result_assembly.py` | কোনো I/O করে না। অসম্পূর্ণ status এর জন্য নিরাপদ মান বসায় (source না থাকলে INCOMPLETE, এবং CONFIRMED না হলে content ও date null)। `confidence` হিসাব করে: CONFIRMED হলে তিনটি measurement এর গড়, NOT_FOUND হলে কত শতাংশ search call সম্পূর্ণ হয়েছে। প্রতিটি মাত্রা আলাদা রেখে সাধারণ ভাষায় `reasoning` লেখে। **Critical।** |
| S13 | `s13_result_persistence.py` | Submission তৈরি বা update (আগেই সম্পন্ন হয়ে থাকলে কিছু করে না)। ranked article সংরক্ষণ (S08 যেটি বেছেছে তার DB id থেকে `top_article_id`)। `upsert_result` (`analysis_details` সহ)। search query log। EXPERT_REVIEW ও phase DONE। ফলাফল reuse করা যায় এমন হলে Redis pointer। submitter কে notification। `total_submissions` বাড়ানো। **Critical।** |

### 9.3 `verification/analysis/`: model ছাড়া বিশুদ্ধ যুক্তি

এই package এর কোনো function I/O করে না এবং কোনো ML model ব্যবহার করে না। তাই এগুলো বাংলা উদাহরণ দিয়ে সরাসরি unit test করা যায়।

| File | কাজ |
|---|---|
| `__init__.py` | Package এর উদ্দেশ্য বর্ণনা করা docstring। |
| `text.py` | তুলনার দুই পাশে একই normalization (`normalize_for_match`: NFC, digit ASCII তে, casefold)। বাংলা অক্ষর বুঝতে পারে এমন tokenizer, `light_stem` (বিভক্তি বাদ দেওয়া: গুলো, দের, কে, তে, টি, র ইত্যাদি)। negation (জোড়া লাগানো রূপ যেমন হয়নি বা করেনি সহ), qualifier এর গোষ্ঠী (সব/কিছু/শুধু/অন্তত/সর্বোচ্চ/প্রায়), stopword। `content_tokens`, `split_sentences`, `chunk_text` (কোনো লেখা বাদ না দিয়ে chunk করে, সীমা ছাড়ালে `truncated` চিহ্ন দেয়)। |
| `keywords.py` | **একমুখী** keyword coverage: claim এর প্রতিটি অর্থপূর্ণ শব্দ evidence এ আছে কিনা। সংখ্যা, negation ও qualifier এর weight ১.৫। দুই শব্দে লেখা যৌগিক শব্দ ও এক শব্দে লেখা একই শব্দ মেলে। state হয় COMPUTED, EMPTY বা UNAVAILABLE, যাতে "মান ০" আর "হিসাব করা যায়নি" আলাদা থাকে। |
| `entities.py` | Entity মেলানো, সতর্কভাবে: হুবহু মিল, ছোট একটি alias তালিকা, একাধিক token এর span, অথবা text এ সরাসরি উপস্থিতি। শুধু একই পদবি মিললে "ambiguous", মিল ধরা হয় না। `mentions_in_sentence`। |
| `passages.py` | Article এর পুরো body এর সাথে headline তুলনা না করে, যে বাক্যগুলো claim নিয়ে কথা বলে সেগুলো (আশেপাশের বাক্যসহ, overlap হলে মিলিয়ে) বেছে নেয়। |
| `decisions.py` | `assess_correspondence` (threshold অনুযায়ী STRONG/PLAUSIBLE/NONE/UNKNOWN; প্রায় হুবহু title না হলে keyword এর সমর্থনও লাগে), `decide_source` (search adequate না হলে কখনো NOT_FOUND নয়), `decide_date`, `search_adequate`, `correspondence_strength`। |
| `headline_comparison.py` | `HeadlineComparator.compare()`: title না থাকলে SOURCE_TITLE_MISSING। হুবহু মিললে MATCHED (শুধু NFC, zero-width, whitespace ও শেষের একটি `।.!?` বাদ দিয়ে)। নাহলে material difference এর নিয়ম ও semantic বিশ্লেষণ দুটোই চলে: NLI দুই দিকে, সাথে LaBSE cosine। verdict এর নিয়ম: কোনো material difference থাকলে ALTERED; একই শব্দ একই ক্রমে থাকলে MATCHED; semantic ভাবে সমতুল্য হলে MATCHED (entailment ≥ ০.৮০, contradiction ≤ ০.২০, cosine ≥ ০.৭০); অর্থ আলাদা হলে ALTERED; model না থাকলে MODEL_UNAVAILABLE; কোনোটাই নিশ্চিত না হলে UNDETERMINED। `METHOD = "headline-title-v1"`। |
| `material_differences.py` | Deterministic নিয়ম, এবং প্রতিটি নিয়ম উদ্ধৃতি সহ প্রমাণ দেয়: **numbers** (একক ও কী গোনা হচ্ছে সহ, যেমন ৫ জন নিহত; লাখ ও কোটি বোঝে), **date** শব্দ, **negation**, **modality** (ঘটে গেছে নাকি পরিকল্পনা), **scope** (qualifier এর বিরোধ), **subject_object** (কে কাকে কী করেছে উল্টে যাওয়া), **attribution** (title এ "অভিযোগ" বা "দাবি" অথচ headline এ তা নিশ্চিত ঘটনা হিসেবে), **denial**, **entity** (NER কাজ করলে)। negation, modality ও scope মিলিয়ে দেখা হয় headline আর title এর মিলে যাওয়া clause এর মধ্যে। |
| `body_similarity.py` | চারটি measurement, প্রতিটি আলাদা ও নিজের availability সহ: TF-IDF cosine (N=2), Jaccard, normalized Levenshtein (২০ হাজার অক্ষর পর্যন্ত), LaBSE cosine (chunk করে প্রতিটি claim chunk এর সবচেয়ে কাছের source chunk, chunk এর দৈর্ঘ্য দিয়ে weighted গড়)। `compare_bodies()` কখনো exception দেয় না। |

---

## 10. `scripts/`

| File | কাজ |
|---|---|
| `seed_verified_sources.py` | `SOURCE_REGISTRY` থেকে `verified_sources` এ insert বা update করে (alias merge করে)। registry এর নিজের docstring বলে চালু DB তে এটি চালানো উচিত নয়। |
| `fix_source_configs.py` | একবার চালানোর জন্য লেখা: কয়েকটি source এর URL pattern, selector ও search URL ঠিক করা (asyncpg দিয়ে সরাসরি SQL)। |
| `reset_operational_data.py` | 2026-10-03 এর cleanup: backup, migration `a6d9e2f4b8c0` চালানো, operational data মুছে ফেলা, এবং protected table ও admin অপরিবর্তিত আছে কিনা যাচাই। শুধু DB revision `d1a7c3e5f9b2` এ চলে। |
| `report_verification_timings.py` | শুধু DB পড়ে: সাম্প্রতিক verification গুলোর pipeline, job ও stage এর সময়ের Markdown report (median ও max)। |

---

## 11. `tests/`

শুধু unit test। `tests/unit/` এর গঠন `app/` এর মতোই: service logic আছে এমন প্রতিটি file এর নিজস্ব `test_<module>.py` আছে (যেমন `app/features/verification/pipeline/stages/s08_source_correspondence.py` → `tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py`)। Router, schema, model ও DI wiring এর জন্য আলাদা test নেই।

| File / folder | কাজ |
|---|---|
| `conftest.py` | App import এর আগে test এর settings ঠিক করে (`.env` এর SMTP ও Gemini key খালি করে দেয়, যাতে test কখনো আসল email না পাঠায়), এবং SQLite এ Postgres ARRAY/JSONB চালানোর shim। |
| `unit/conftest.py` | `db` / `session` (in-memory SQLite) ও `file_db` (background worker এর জন্য file-backed) fixture। |
| `helpers/db.py` | সব table তৈরি করে, এবং user, source, submission, result, multimodal analysis, voting config বানানোর ছোট helper। |
| `helpers/pipeline.py` | ML service এর deterministic নকল (embedding, NLI, NER), `make_context`, `run_analysis` (S08–S12) ও নকল source registry। এগুলো যুক্তি পরীক্ষার জন্য, model এর accuracy সম্পর্কে কিছু প্রমাণ করে না। |
| `helpers/gemini.py`, `helpers/playwright.py`, `helpers/multimodal.py` | নকল Gemini endpoint, নকল Playwright browser, এবং ছোট নকল BanglaBERT/EfficientNet loader। |
| `unit/core/`, `unit/shared/` | Settings এর নিয়ম, lifespan, এবং shared utility (hashing এর golden value সহ)। |
| `unit/verification/analysis/` | Headline comparison, material difference, body similarity, keyword, entity, decision। |
| `unit/verification/pipeline/` | Context, factory, orchestrator, এবং S01–S13 প্রতিটি stage আলাদা করে। |
| `unit/verification/` | Service (registration, reuse), presenter, source policy, reuse, job queue ও worker। |
| `unit/<feature>/` | auth, admin, dashboard, expert_review, multimodal, notifications, photocard, search, sources, submissions, users, nlp, cache: প্রতিটি service ও logic file এর জন্য একটি করে। |

## 12. Database table ও তাদের মালিক

| Table | ORM class | কোন file এ | কে লেখে |
|---|---|---|---|
| `users` | `User` | `auth/models.py` | auth, admin, S13/multimodal (counter) |
| `refresh_tokens`, `password_reset_tokens` | `RefreshToken`, `PasswordResetToken` | `auth/models.py` | auth |
| `verified_sources` | `VerifiedSource` | `sources/models.py` | sources (admin), seed script |
| `submissions` | `Submission` | `submissions/models.py` | verification, photocard, multimodal, review |
| `source_evidence_queries` | `SourceEvidenceQuery` | `submissions/models.py` | S13 (শুধু লেখা হয়) |
| `retrieved_articles` | `RetrievedArticle` | `submissions/models.py` | S13 |
| `photocard_extractions` | `PhotocardExtraction` | `submissions/models.py` | photocard |
| `verification_results` | `VerificationResult` | `verification/models.py` | S13, reuse, expert review (overall) |
| `verification_jobs` | `VerificationJob` | `verification/models.py` | job repository ও worker |
| `multimodal_analysis` | `MultimodalAnalysis` | `multimodal/models.py` | multimodal, expert review |
| `expert_profiles`, `expert_reviews`, `credibility_weight_tiers`, `voting_config` | একই নামের class | `expert_review/models.py` | expert review, admin |
| `notifications`, `result_deliveries` | `Notification`, `ResultDelivery` | `notifications/models.py` | notifications, escalation, jobs |
| `alembic_version` | — | — | Alembic |
