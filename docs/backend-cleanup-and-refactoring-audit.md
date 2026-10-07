# Backend Cleanup ও Refactoring Audit

> **তারিখ:** 2026-10-07 · **পরিধি:** `backend/` ফোল্ডারের সব source, config, `.env`, `.env.example`, script, migration ও test
> **গুরুত্বপূর্ণ:** এই document শুধু বিশ্লেষণ ও পরামর্শ। কোনো code পরিবর্তন করা হয়নি।
> **বাদ রাখা হয়েছে:** `app/features/verification/pipeline/source_registry.py`। এই file এ কোনো পরিবর্তনের পরামর্শ দেওয়া হয়নি এবং এটি delete list এও নেই। প্রস্তাবিত নতুন structure এও file টি একই জায়গায় থাকবে।

প্রতিটি "অব্যবহৃত" দাবি `grep` ও AST-based reference count দিয়ে যাচাই করা হয়েছে (app + scripts + tests)। frontend (`frontend/src`) ও extension (`extension/src`) কোন endpoint call করে, সেটাও মিলিয়ে দেখা হয়েছে।

সব প্রস্তাবের একটাই শর্ত: **বাইরে থেকে দেখা আচরণ (API response, DB data, verification ফলাফল) একই থাকবে।** যেখানে কোনো পরিবর্তন আচরণে প্রভাব ফেলতে পারে, সেখানে আলাদা করে উল্লেখ করা আছে।

---

## সূচিপত্র

1. [জরুরি সমস্যা (আগে ঠিক করা উচিত)](#1-জরুরি-সমস্যা-আগে-ঠিক-করা-উচিত)
2. [Delete করার মতো file ও folder](#2-delete-করার-মতো-file-ও-folder)
3. [অব্যবহৃত constant, enum ও global variable](#3-অব্যবহৃত-constant-enum-ও-global-variable)
4. [অব্যবহৃত settings field ও `.env` variable](#4-অব্যবহৃত-settings-field-ও-env-variable)
5. [অব্যবহৃত exception class](#5-অব্যবহৃত-exception-class)
6. [অব্যবহৃত function, method, class, field, endpoint ও DB column](#6-অব্যবহৃত-function-method-class-field-endpoint-ও-db-column)
7. [Comment ও docstring নিয়ে মতামত](#7-comment-ও-docstring-নিয়ে-মতামত)
8. [অনুচিত default value](#8-অনুচিত-default-value)
9. [এক file এ একাধিক দায়িত্ব বা class: ভাগ করার পরামর্শ](#9-এক-file-এ-একাধিক-দায়িত্ব-বা-class-ভাগ-করার-পরামর্শ)
10. [Duplicate code (DRY লঙ্ঘন)](#10-duplicate-code-dry-লঙ্ঘন)
11. [OOP ও SOLID নীতি অনুযায়ী redesign](#11-oop-ও-solid-নীতি-অনুযায়ী-redesign)
12. [Global state, lifecycle ও transaction boundary](#12-global-state-lifecycle-ও-transaction-boundary)
13. [প্রস্তাবিত Package-by-Feature structure](#13-প্রস্তাবিত-package-by-feature-structure)
14. [ধাপে ধাপে করার পরিকল্পনা](#14-ধাপে-ধাপে-করার-পরিকল্পনা)

---

## 1. জরুরি সমস্যা (আগে ঠিক করা উচিত)

refactoring শুরুর আগেই এগুলো ঠিক করা দরকার, কারণ এগুলো security বা সঠিকতার সমস্যা।

| # | সমস্যা | কোথায় | কেন গুরুতর | পরামর্শ |
|---|---|---|---|---|
| 1.1 | **JWT একটি hardcoded default secret দিয়ে sign হচ্ছে** | `core/config.py` এর `AuthSettings.secret_key` (env: `AUTH_SECRET_KEY`), ব্যবহার হয় `auth/security.py:56,75` এ | `.env` এ শুধু `SECRET_KEY` আছে। ওটা `AppSettings.secret_key` এ যায়, যা কোথাও ব্যবহার হয় না। `AUTH_SECRET_KEY` নেই, তাই সব token `"CHANGE_ME_IN_PRODUCTION_USE_STRONG_RANDOM_SECRET_32CHARS"` দিয়ে sign হচ্ছে। এই string public repo তে আছে, তাই যে কেউ admin token বানাতে পারবে। | `.env` এ `AUTH_SECRET_KEY` যোগ করুন। code এ `secret_key` এর default সরিয়ে required field বানান (`Field(..., min_length=32)`), যাতে secret না থাকলে app চালু-ই না হয় (fail-fast)। অব্যবহৃত `AppSettings.secret_key` মুছে দিন। |
| 1.2 | `.env.example` এ আসল দেখতে একটি SMTP app password | `backend/.env.example` এর `EMAIL_SMTP_PASSWORD` | এই file git এ tracked। মান টি Gmail app password এর ফরম্যাটে লেখা। | Google account থেকে ঐ app password revoke করুন। `.env.example` এ মান খালি রাখুন। |
| 1.3 | `CORS allow_origins=["*"]` এবং `allow_credentials=True` একসাথে | `core/config.py` (`cors_origins` default), `main.py` | wildcard origin এর সাথে credentials অনুমোদন করা নিরাপদ নয় (browser এটা প্রত্যাখ্যানও করে)। | `cors_origins` এর default খালি list রাখুন এবং `.env` থেকে নির্দিষ্ট origin (frontend URL, extension origin) দিন। |
| 1.4 | Embedding model এর setting আর আসল model আলাদা | `nlp/embedding_service.py:19` এ `_MODEL_NAME = "sentence-transformers/LaBSE"` hardcoded। `.env`/config এ `ML_EMBEDDING_MODEL_NAME=paraphrase-multilingual-mpnet-base-v2` | setting এর মান অনুযায়ী model load হয় না। `photocard/verification_stages.py:22` এ claim hash এর মধ্যে `embedding_model_name` ঢোকে, তাই hash এর "model identity" ভুল তথ্য বহন করে। | config এর `embedding_model_name` এর default `sentence-transformers/LaBSE` করুন এবং service এ সেটাই পড়ুন। `.env` এর মান LaBSE তে বদলান (নাহলে আচরণ বদলে যাবে)। `body_similarity.SEMANTIC_MODEL` এও একই মান ব্যবহার করুন। |
| 1.5 | Model weight (`classifier.pt`, 13 MB) git এ committed | `app/features/multimodal/multimodal_model/classifier.pt` | `.gitignore` এ `*.pt` থাকার পরও এটি tracked। বাকি দুটি `.pt` (488 MB) untracked, তাই repo clone করলে model অসম্পূর্ণ পাওয়া যায়। | `git rm --cached` করুন। তিনটি weight-ই Git LFS বা release asset/Drive এ রাখুন এবং README তে download এর ধাপ লিখুন। |
| 1.6 | `requirements.txt` / `pyproject.toml` এ dependency অসম্পূর্ণ | — | code এ `python-jose`, `bcrypt`, `email-validator` (EmailStr), `psycopg2` (Alembic sync URL), `playwright` import হয়, কিন্তু কোনো dependency file এ নেই। `pyproject.toml` এ `minio`, `timm`, `torchvision`, `Pillow`, `numpy` নেই। অন্যদিকে `feedparser` ও `tenacity` আছে, কিন্তু চালু code এ ব্যবহার হয় না (`tenacity` শুধু অব্যবহৃত `retry.py` তে)। | একটি মাত্র উৎস রাখুন (`pyproject.toml`) এবং `requirements.txt` সেখান থেকে generate করুন (`pip-compile`)। অনুপস্থিত package গুলো যোগ করুন, অব্যবহৃতগুলো বাদ দিন। |
| 1.7 | Admin এর email ও password hash migration এ hardcoded | `migrations/versions/20260707_1200_seed_admin_user_001.py` | default admin account সবার জানা। | চালু DB তে admin এর password বদলান। ভবিষ্যতের জন্য admin তৈরি একটি CLI command দিয়ে করুন, যা env থেকে মান নেয় (migration টি history হিসেবে থাকবে, সেটা মুছবেন না)। |
| 1.8 | Login এর timing-attack সুরক্ষা কাজ করে না | `auth/service.py:106` এর `_dummy_hash` | dummy hash টি বৈধ bcrypt hash নয়, তাই `bcrypt.checkpw` সঙ্গে সঙ্গে `ValueError` দেয়। ফলে অজানা email এর উত্তর অনেক দ্রুত আসে, এবং কোন email registered তা আঁচ করা যায়। | module load এর সময় একবার `hash_password("dummy")` দিয়ে একটি বৈধ dummy hash তৈরি করুন। |

---

## 2. Delete করার মতো file ও folder

### 2A. নিশ্চিন্তে delete করা যায় (আচরণে কোনো প্রভাব নেই)

| Path | কারণ |
|---|---|
| `app/shared/utils/retry.py` | কোনো module এটি import করে না। docstring এ পুরোনো path (`app/utils/retry.py`) ও এমন Brave API এর উল্লেখ আছে, যা এখন project এ নেই। এটি মুছলে `tenacity` dependency ও বাদ দেওয়া যায়। |
| `app/features/feedback/` | এখানে কোনো `.py` file নেই, শুধু পুরোনো `__pycache__`। feature টি আগেই সরানো হয়েছে। |
| সব `__pycache__/` (tracked 9টি `.pyc` সহ) | `git ls-files` এ ৯টি `.pyc` আছে (`app/__pycache__/*.pyc`, `app/api/v1/__pycache__/*`, `app/db/migrations/__pycache__/*`, `tests/__pycache__/*` ইত্যাদি)। এছাড়া disk এ ৪০টির বেশি **orphan** `.pyc` আছে, যাদের source এখন নেই (`ocr_fallback_extractor`, `s08_similarity_analyzer`, `google_cse_client`, `newsdata_client`, `duckduckgo_client` ইত্যাদি)। এগুলো grep এর ফলাফল বিভ্রান্ত করে (যেমন `GEMINI_MIN_GROUNDING_OVERLAP` শুধু একটি পুরোনো `.pyc` তে পাওয়া যায়)। `git rm -r --cached '**/__pycache__'` চালান এবং disk থেকেও মুছে দিন। |
| `backend/coverage.xml` | এটি generated file হলেও git এ tracked (400 KB), যদিও `.gitignore` এ আছে। `git rm --cached` করুন। |
| `backend/.coverage` | generated file। untracked, disk থেকে মুছে দেওয়া যায়। |
| `scripts/fix_source_configs.py` | এটি একবার চালানোর জন্য লেখা maintenance script। এর মান গুলো এখন DB snapshot এর সাথে **মেলে না**, যেমন `dailynayadiganta.com` এর pattern আর `mzamin.com` এর `internal_search_url` (`source_registry.py` এর 2026-10-03 snapshot দেখুন)। আবার চালালে DB এর data পুরোনো অবস্থায় ফিরে যাবে। script টি git history তে থেকে যাবে। |
| `scripts/reset_operational_data.py` | 2026-10-03 এর একবারের cleanup script। এটি শুধু DB revision `d1a7c3e5f9b2` এ চলে এবং অন্য কোনো revision পেলে চলতে অস্বীকার করে। DB এখন `f3b7d1e9a2c4` এ আছে, এবং যে `user_profiles` table এর উপর এটি নির্ভর করে সেটিও মুছে ফেলা হয়েছে। তাই এটি আর চালানো সম্ভব নয়। `docs/database-cleanup-2026-10-03.md` এ এর উল্লেখ থাকলে লিখে দিন যে script টি git history তে আছে। |

### 2B. শর্তসাপেক্ষে delete করা যায় (আগে সিদ্ধান্ত নিতে হবে)

| Path / অংশ | অবস্থা | সিদ্ধান্তের শর্ত |
|---|---|---|
| `scripts/seed_verified_sources.py` | `SOURCE_REGISTRY` এর একমাত্র ব্যবহারকারী। অথচ `source_registry.py` এর নিজের docstring বলে: *"Never run the seed script to synchronize this file back into the live database."* script টি `display_name_en`, `search_language`, `js_rendered`, `is_active` এর মতো field উপেক্ষা করে, এবং alias merge করার সময় `set()` ব্যবহার করে বলে alias এর ক্রম হারিয়ে যায়। | **বিকল্প ক:** delete করুন (registry তখন শুধু reference হিসেবে থাকবে, যেমন তার docstring বলে)। **বিকল্প খ:** নাম `bootstrap_empty_sources.py` করে একটি guard যোগ করুন, যাতে `verified_sources` table খালি না থাকলে script চলতে অস্বীকার করে। এতে নতুন developer machine সেটআপ করা সহজ থাকে। দুই ক্ষেত্রেই `source_registry.py` অপরিবর্তিত থাকবে। |
| Sync endpoint `POST /api/v1/verify` | frontend বা extension এর কোনো component এটি call করে না (frontend এর `VerificationService.submit()` আছে, কিন্তু কোথাও ব্যবহার হয় না)। শুধু integration test এ ব্যবহার হয়। | public API contract বলে, বাইরের কোনো consumer না থাকলে তবেই সরান। তখন test গুলো `/verify/async` এ সরাতে হবে। |
| Sync endpoint `POST /api/v1/multimodal/predict` | একই অবস্থা (frontend এর `MultimodalService.predict()` ব্যবহার হয় না)। শুধু `tests/integration/test_multimodal_router.py` এ ব্যবহার হয়। | উপরের মতো। সরালে `MultimodalPredictionService.predict()` এর `_create_submission` path ও অপ্রয়োজনীয় হয়ে যায়। |
| `GET /multimodal/predict/{prediction_id}`, `GET /multimodal/predictions` | কোনো client call করে না। এছাড়া `list_predictions` এ একটি bug আছে: `total = len(records)`, অর্থাৎ total হিসেবে মোট সংখ্যার বদলে শুধু বর্তমান page এর সংখ্যা ফেরত যায়। | রাখলে bug ঠিক করুন, না রাখলে সরান। |
| `GET /dashboard/stats`, `GET /dashboard/top-sources`, `GET /admin/stats`, `GET /expert/credibility` | frontend এর service এ wrapper method আছে, কিন্তু কোনো component সেগুলো call করে না। | UI এর পরিকল্পনা অনুযায়ী সিদ্ধান্ত নিন। রাখলে সংশ্লিষ্ট query logic router থেকে repository/service এ সরান (section 9 দেখুন)। |
| `app/features/articles/` (পুরো package) | এখানে শুধু `schemas.py` আছে। এগুলো আসলে pipeline এর internal DTO, কোনো আলাদা feature নয়। এর মধ্যে `ExtractedContentSchema` ও `ArticleExtractionResult` কোথাও ব্যবহার হয় না। | package টি delete করুন এবং `CandidateArticleSchema` ও `RankedArticleSchema` কে `verification/evidence/schemas.py` তে সরান (section 13 দেখুন)। |
| `app/features/verification/verdict_compat.py` | এতে আছে শুধু একটি formatter function, আর একটি লম্বা "history" docstring। নামটিও ("compat") বিভ্রান্তিকর। | `format_verdict_display()` কে `shared/status_labels.py` তে সরিয়ে file টি delete করুন। |

### 2C. Delete করবেন না, কিন্তু অবস্থান বা ব্যবস্থাপনা বদলান

| Path | পরামর্শ |
|---|---|
| `app/db/migrations/versions/*.py` (মোট ২৮টি) | কোনো migration delete করবেন না। এগুলো একটি chain, এবং চালু DB এর `alembic_version` এর সাথে মিলতে হবে। চাইলে ভবিষ্যতে নতুন deployment এর জন্য একটি "squashed baseline" migration বানাতে পারেন, কিন্তু পুরোনোগুলো রেখেই। |
| `app/features/multimodal/multimodal_model/` | weight file গুলো code tree থেকে সরিয়ে `MULTIMODAL_MODEL_DIR` দিয়ে বাইরের একটি জায়গায় রাখুন। `config.json` এ Colab এর training path (`/content/drive/...`) ও training hyper-parameter আছে, runtime এ এগুলোর কোনোটাই পড়া হয় না। `MultimodalSettings` এ একই মান আবার hardcoded আছে (`num_classes`, `dropout`, `img_size`, `max_seq_length`)। হয় loader কে `config.json` থেকে মান পড়ান, নয়তো file টিকে শুধু documentation হিসেবে রাখুন। |
| `run.py` ও `main.py` এর Windows event loop policy | একই কোড দুই জায়গায় আছে (এবং আরও দুটি Playwright helper এ)। একটি `core/platform.py` তে রাখুন। |

---

## 3. অব্যবহৃত constant, enum ও global variable

### `app/core/constants.py`

| নাম | অবস্থা | পরামর্শ |
|---|---|---|
| `ClaimStatus` (enum) | কোথাও ব্যবহার হয় না | delete করুন |
| `LogLevel` (enum) | কোথাও ব্যবহার হয় না (log level validation `config.py` তে set দিয়ে হয়) | delete করুন |
| `JobPhase` (enum) | enum টি ব্যবহার হয় না, **কিন্তু এর মানগুলো ১২টির বেশি জায়গায় raw string হিসেবে লেখা** (`"QUEUED"`, `"EXTRACTING"`, `"VERIFYING"`, `"DONE"`, `"FAILED"`) | delete না করে **ব্যবহার করুন**। `Submission.processing_phase`, `set_phase()`, `mark_ai_done()` ও সব response field এ `JobPhase` বসান। |
| `MAX_CONCURRENT_FETCHES = 10` | অব্যবহৃত। S05 এ আলাদা local মান `_MAX_CONCURRENT_FETCHES = 8` আছে, যা বিভ্রান্তিকর। | delete করুন, অথবা S05 এর local মানের বদলে এটি ব্যবহার করুন (8 রাখলে আচরণ একই থাকবে) |
| `MAX_EVIDENCE_CANDIDATES = 5` | অব্যবহৃত (প্রকৃত সীমা `MLSettings.max_ranked_articles`) | delete করুন |
| `MIN_KEYWORD_OVERLAP = 0.10` | অব্যবহৃত | delete করুন |
| `REDIS_KEY_PREFIX = "bgf"` | অব্যবহৃত, অথচ `"bgf:"` prefix টি `cache_service.py` ও `embedding_service.py` তে hardcoded | delete না করে **ব্যবহার করুন** (key এর নামকরণ এক জায়গায় আনুন) |
| `ExpertVerdict` | শুধু legacy column `ai_consensus_label` এর জন্য দরকার | column থাকা পর্যন্ত রাখুন, তারপর একসাথে সরান |
| `MetricState.NOT_APPLICABLE` | কোনো code এটি তৈরি করে না | docstring থেকে উল্লেখটি সরিয়ে member টি বাদ দেওয়া যায় |
| `SearchProvider.NEWSDATA`, `GOOGLE_CUSTOM_SEARCH`, `SEARXNG`, `DDG`, `BRAVE`, `GOOGLE_RSS` | চালু code এ কোনো provider নেই। `GOOGLE_RSS` শুধু S06 এ একটি **ভুল fallback** হিসেবে আছে। | এগুলো Postgres enum `search_provider_enum` এর মান, এবং পুরোনো row এ থাকতে পারে। DB তে কোনো row এ এই মান না থাকলে migration দিয়ে enum ছোট করুন, নাহলে `# legacy DB value` চিহ্ন দিয়ে আলাদা রাখুন। |
| `QueryType.ENTITIES`, `BODY_SUMMARY`, `SITE_RESTRICTED` | কেউ এই query type তৈরি করে না | উপরের মতো (DB enum) |
| `KNOWN_SOURCE_ALIASES` | ব্যবহার হয়, **কিন্তু design এর সমস্যা আছে** | section 11.6 দেখুন। এর ভেতরে `banglatribune.com`, `dhakatribune.com`, `bdnews24.com`, `rtvonline.com`, `somoynews.tv`, `channel24bd.tv` আছে, যেগুলো `verified_sources` এ নেই। ফলে resolution এমন domain ফেরত দিতে পারে যা DB তে নেই। এছাড়া কোনো source DB তে deactivate করা থাকলেও এই static map দিয়ে resolve হয়ে যায়। |

### অন্যান্য module-level constant / global

| File | নাম | অবস্থা |
|---|---|---|
| `features/cache/cache_service.py` | `_KEY_EMBEDDING`, `_KEY_ARTICLE` | `_KEY_EMBEDDING` কোথাও ব্যবহার হয় না। `_KEY_ARTICLE` শুধু অব্যবহৃত method এ। embedding service নিজে আলাদা করে `"bgf:emb"` লেখে। |
| `features/nlp/embedding_service.py` | `_EMBEDDING_DIM = 768` | অব্যবহৃত |
| `features/nlp/embedding_service.py` | `_CACHE_TTL_SECONDS = 86_400` | hardcoded। এর জন্য config এ `ttl_embedding` (172800) আছে কিন্তু পড়া হয় না। আচরণ একই রাখতে চাইলে config এর মান 86400 করে এখানে সেটাই পড়ুন। |
| `features/photocard/claim_extraction.py` | `STATUS_PENDING` | অব্যবহৃত, অথচ `photocard/service.py:127` এ `"PENDING"` raw string হিসেবে লেখা। এই status গুলোর জন্য একটি `ExtractionStatus` enum বানান। |
| `features/verification/pipeline/stages/s06_article_extractor.py` | `_BANGLA_TO_ARABIC`, `_BANGLA_MONTHS`, `_DATE_FORMATS`, `_parse_date()` | **dead code**। এগুলো শুধু `_extract_bs4()` এর `pub_date` হিসাব করতে ব্যবহার হয়, আর caller (`bs_date`) সেই মান ফেলে দেয়। trafilatura এর `t_date` ও সবসময় `None`। |
| `features/verification/pipeline/stages/s06_article_extractor.py` | `_TITLE_SUFFIX_RE` | outlet এর নাম hardcoded, অথচ এই তথ্য DB তে (`verified_sources.display_name/aliases`) আছে। নতুন source যোগ হলে regex update করতে হয়। |
| `features/verification/analysis/material_differences.py` | `__all__` এর মধ্যে `QUALIFIER_WORDS` | এখান থেকে export হয় কিন্তু কেউ import করে না (এটি `text.py` এর জিনিস) |
| `features/multimodal/pipeline/*` | `_IMG_MEAN`, `_IMG_STD` | দুটি file এ duplicate |

---

## 4. অব্যবহৃত settings field ও `.env` variable

### 4.1 `core/config.py` এ এমন field যা কোথাও পড়া হয় না

| Class.field | মন্তব্য |
|---|---|
| `AppSettings.app_name`, `app_version` | `main.py` তে `title="BanglaFactGuard"` ও `version="1.0.0"` hardcoded। এছাড়া `pyproject` এ version `1.0.0`, `.env` এ `0.1.0`, health response এ `"1.0.0"`, অর্থাৎ চার জায়গায় তিন রকম মান। একটি জায়গা থেকে পড়ুন। |
| `AppSettings.api_v1_prefix` | `api/v1/router.py` এ `"/api/v1"` hardcoded |
| `AppSettings.debug` | কোথাও পড়া হয় না |
| `AppSettings.api_key_header` | অব্যবহৃত (API key auth বলে কিছু নেই) |
| `AppSettings.secret_key` | অব্যবহৃত (section 1.1 দেখুন) |
| `AppSettings.request_timeout_seconds`, `max_headline_length`, `max_body_length` | অব্যবহৃত। এই সীমাগুলো schema তে আলাদা করে hardcoded (`max_length=2000`, `50_000`)। schema গুলো যেন এই setting থেকে মান নেয়। |
| `AppSettings.classification` (property) | `thresholds` এরই আরেকটি নাম (alias), অপ্রয়োজনীয়। একটিই রাখুন। |
| `RedisSettings.decode_responses` | `lifespan.py` তে `decode_responses=False` hardcoded |
| `RedisSettings.ttl_embedding`, `ttl_nli_output`, `ttl_source_lookup` | অব্যবহৃত |
| `RedisSettings.ttl_article_content` | শুধু অব্যবহৃত `CacheService.set_article` এ ব্যবহার হয় |
| `MLSettings.device`, `use_fp16`, `cache_dir` | অব্যবহৃত। NER ও NLI তে `device=-1` hardcoded, অর্থাৎ `ML_DEVICE` দিলেও কোনো প্রভাব পড়ে না। |
| `MLSettings.embedding_model_name` | section 1.4 দেখুন |
| `MLSettings.embedding_max_seq_length` | নাম "seq_length" (token সংখ্যা বোঝায়) হলেও `max_text_chars_for_embedding` হিসেবে **character** সীমা হিসেবে ব্যবহার হয়। নামটি বিভ্রান্তিকর, `embedding_max_chars` করুন। |
| `SearchSettings.pygooglenews_timeout_seconds` | অব্যবহৃত। internal site client এ `timeout=12.0` hardcoded। |
| `AuthSettings.initial_expert_credibility` | নিজের description এ "Deprecated" লেখা, কোথাও পড়া হয় না |
| `AuthSettings.min_expert_votes_to_finalize` | অব্যবহৃত, আসল মান DB এর `voting_config` এ থাকে |

### 4.2 `.env` এ আছে কিন্তু কোনো setting এ map হয় না বা ব্যবহার হয় না

| Variable | অবস্থা |
|---|---|
| `SECRET_KEY` | অব্যবহৃত field এ যায় (section 1.1) |
| `APP_NAME`, `APP_VERSION`, `DEBUG`, `API_V1_PREFIX` | অব্যবহৃত field |
| `THRESHOLD_TRUE_MIN_SEMANTIC_SIMILARITY`, `THRESHOLD_TRUE_MIN_ENTITY_MATCH`, `THRESHOLD_TRUE_MAX_CONTRADICTION`, `THRESHOLD_FALSE_MIN_CONTRADICTION`, `THRESHOLD_PARTIAL_MIN_SEMANTIC_SIMILARITY`, `THRESHOLD_NOT_FOUND_MAX_SEMANTIC_SIMILARITY`, `THRESHOLD_MIN_EVIDENCE_THRESHOLD` | `ClassificationThresholds` এ এই নামের কোনো field নেই। পুরোনো TRUE/FALSE verdict model এর অবশিষ্ট, তাই নীরবে উপেক্ষিত হয়। মুছে দিন। |
| `GEMINI_MIN_GROUNDING_OVERLAP` | কোনো setting নেই, শুধু একটি orphan `.pyc` তে পাওয়া যায় |
| `REDIS_TTL_EMBEDDING`, `REDIS_TTL_NLI_OUTPUT`, `REDIS_TTL_SOURCE_LOOKUP`, `REDIS_TTL_ARTICLE_CONTENT` | অব্যবহৃত field |
| `ML_EMBEDDING_MODEL_NAME`, `ML_DEVICE`, `ML_USE_FP16` | এগুলো set করলেও আচরণ বদলায় না |
| `REDIS_PASSWORD` (মান খালি) | কোনো সমস্যা নেই, তবে `.env.example` এর মতো লাইনের শেষে মন্তব্যের জায়গা রাখলে ভালো |

### 4.3 `.env.example` এর সমস্যা

* `REDIS_TTL_CLAIM_RESULT` দুইবার লেখা আছে।
* সবচেয়ে গুরুত্বপূর্ণ `AUTH_SECRET_KEY` নেই। `JOBS_*`, `GEMINI_BASE_URL`, `PHOTOCARD_MAX_IMAGE_BYTES`, `EMAIL_WEBSITE_URL`, `CORS_ORIGINS` এর অবস্থাও একই রকম অসম্পূর্ণ।
* `SEARCH_TOP_K_CANDIDATES=5` দেওয়া, অথচ code এর default 15। example অনুযায়ী `.env` বানালে আচরণ বদলে যায়।
* `MULTIMODAL_MODEL_DIR` example ও `.env` এ আলাদা।
* **পরামর্শ:** settings class থেকে স্বয়ংক্রিয়ভাবে `.env.example` তৈরি করুন (`pydantic-settings` model iterate করে একটি ছোট script), যাতে দুটো কখনো আলাদা না হয়।

---

## 5. অব্যবহৃত exception class

`core/exceptions.py` তে মোট ৪০টি class আছে, তার মধ্যে নিচেরগুলো কখনো raise বা catch হয় না:

| Class | পরামর্শ |
|---|---|
| `SourceNormalizationError` | delete |
| `CacheError`, `SearchError`, `ExtractionError`, `SimilarityError`, `NLIError` | delete (বিদ্যমান `StageError` subclass গুলোই যথেষ্ট) |
| `CacheBackendError` | delete |
| `SearXNGError`, `BraveAPIError`, `GoogleRSSError` | delete। এই provider গুলো project থেকে অনেক আগেই সরানো হয়েছে। |

উল্টো সমস্যা: কিছু exception ভুল জায়গায় define করা।
* `MultimodalStorageError` আছে `multimodal/storage_service.py` তে।
* `InternalSiteSearchError` আছে `search/internal_site_client.py` তে, যদিও এর সমগোত্রীয় `PyGoogleNewsError` আছে `core` এ।
* `_OriginBlocked`, `_RedirectRejected` exception হলেও `raise` না হয়ে **return** হয় (S05)।

পরামর্শ: প্রতিটি feature এর নিজের `exceptions.py` রাখুন (package-by-feature)। `core/exceptions.py` তে থাকবে শুধু base class (`BanglaFactGuardError`, `DomainValidationError`, `RecordNotFoundError`, `AuthError`, `PermissionDeniedError`)।

---

## 6. অব্যবহৃত function, method, class, field, endpoint ও DB column

### 6.1 Function / method / class (app এ ০ reference)

| File | Symbol | মন্তব্য |
|---|---|---|
| `core/logging.py` | `get_logger`, `bind_request_context`, `clear_context` | request context কখনো log এ bind হয় না। হয় middleware এ `bind_request_context` ব্যবহার করুন, নয়তো delete করুন। |
| `db/engine.py` | `check_db_connection`, `close_engine`, `get_db_context` | অব্যবহৃত। `lifespan` shutdown এ `close_engine()` call করা উচিত ছিল, এখন engine pool dispose হয় না। |
| `db/engine.py` | `get_async_session` | `shared/dependencies.py` তে **একই নামে আরেকটি** function আছে। `multimodal/router.py` ব্যবহার করে db version টি, বাকি সব router ব্যবহার করে shared version টি। একটি রাখুন। |
| `shared/base_repository.py` | `get_by_field`, `exists` | অব্যবহৃত |
| `shared/status_labels.py` | `OVERALL_LABELS` | অব্যবহৃত (delivery.py নিজে `.capitalize()` করে) |
| `shared/utils/text_cleaner.py` | `extract_first_n_sentences` | অব্যবহৃত |
| `features/articles/schemas.py` | `ExtractedContentSchema`, `ArticleExtractionResult` | পুরো class দুটিই অব্যবহৃত |
| `features/auth/repository.py` | `UserRepository.get_active_by_email`, `RefreshTokenRepository.delete_expired` | অব্যবহৃত। `delete_expired` কে একটি periodic cleanup job এ ব্যবহার করলে কাজে লাগবে, কারণ এখন refresh token table শুধু বাড়তেই থাকে। |
| `features/auth/service.py` | `AuthService.get_me` | অব্যবহৃত। router নিজেই private `_to_me_response` import করে। |
| `features/cache/cache_service.py` | `get_article`, `set_article` | অব্যবহৃত |
| `features/expert_review/repository.py` | `get_queue_for_expert`, `count_by_expert`, `get_or_create(initial_score=...)` এর parameter | queue logic service এ সরাসরি SQL দিয়ে লেখা হয়েছে, তাই repository method টি অব্যবহৃত |
| `features/sources/repository.py` | `add_alias` | অব্যবহৃত |
| `features/submissions/repository.py` | `SourceEvidenceQueryRepository` (পুরো class), `SubmissionRepository.get_by_content_hash`, `get_by_date_range`, `get_recent`, `get_verified_by_content_hash` (শুধু test এ), `RetrievedArticleRepository.get_top_ranked`, `count_for_submission`, `update_rank_score` | অব্যবহৃত |
| `features/verification/repository.py` | `get_results_by_source_status` | অব্যবহৃত |
| `features/verification/schemas.py` | `VerificationResultSummary` | অব্যবহৃত |
| `features/verification/analysis/keywords.py`, `entities.py`, `passages.py` | `KeywordCoverage.to_dict`, `KeywordUnit.to_dict`, `EntityMention.to_dict`, `EntityMatch.to_dict`, `Passage.to_dict` | অব্যবহৃত serializer |
| `features/multimodal/pipeline/inference_engine.py` | `PredictionResult.raw_logits` | শুধু test এ ব্যবহার হয়, persist বা return হয় না |
| `features/photocard/gemini_image_extractor.py` | `reset_key_pools` | শুধু test এ, রাখা যায় |

### 6.2 অব্যবহৃত parameter

| জায়গা | Parameter |
|---|---|
| `admin/service.py` | `create/update/delete_credibility_tier(admin_id)`, `update_voting_config(admin_id)`। audit log না থাকায় কোনো কাজে আসে না। `_validate_tier(weight=...)` ও কখনো পড়া হয় না। |
| `users/router.py:get_my_profile` | `session` |
| `s04_source_search.py` | `_should_dispatch(query_type, query_text)` (method টি সবসময় True ফেরত দেয়), `_adapt_query(query_type)` |
| `s07_evidence_ranker.py:_score_article` | `claim_date` |
| `expert_review/repository.py:get_or_create` | `initial_score` ("Legacy caller compatibility") |

### 6.3 শুধু লেখা হয় কিন্তু কখনো পড়া হয় না (write-only) এমন field

| Field | মন্তব্য |
|---|---|
| `PipelineContext.result_id`, `PipelineContext.persisted` | S13 লেখে, কেউ পড়ে না |
| `ExpertHistoryItemResponse.final_source_status/final_content_status/final_date_status` | কখনো set হয় না, সবসময় `null` |
| `VerificationResponse.was_overridden` | "Deprecated, always false" |
| `ExpertProfile.completed_reviews_count` | সবসময় `total_votes` এর সমান মান লেখা হয় |

### 6.4 এমন DB column যা code পড়ে না (সরাতে migration লাগবে)

| Table.column | মন্তব্য |
|---|---|
| `submissions.is_published`, `submissions.view_count` | ORM এ আছে কিন্তু কেউ পড়ে বা লেখে না |
| `expert_profiles.credential_notes`, `expert_profiles.is_active` | অব্যবহৃত (expert এর active অবস্থা `users.is_active` থেকে নেওয়া হয়) |
| `verification_results.ai_preliminary_label` | কেউ লেখে না |
| `verification_results.final_source_status/final_content_status/final_date_status` | কেউ লেখে না (comment এ লেখা "Written only by ExpertReviewService", অথচ ঐ service আর এগুলো লেখে না) |
| `verification_results.ai_consensus_label` | legacy। পুরোনো data সংরক্ষণের জন্য রাখা হয়েছে, সিদ্ধান্ত নিয়ে সরান। |
| `source_evidence_queries` (পুরো table) | শুধু লেখা হয়, পড়া হয় না। আবার যে `search_provider` লেখা হয় সেটিও ভুল (প্রথম candidate এর provider সব query তে বসে যায়)। analytics এ ব্যবহারের পরিকল্পনা না থাকলে সরান। |

> DB column সরানো ঐচ্ছিক, এবং একটি নতুন migration এর মাধ্যমে করতে হবে। এগুলো রেখে দিলেও আচরণে কোনো সমস্যা হয় না।

---

## 7. Comment ও docstring নিয়ে মতামত

### 7.1 আপনার উদাহরণ (`s02_cache_lookup.py` এর `CacheLookupStage` docstring) কি দরকারি?

**হ্যাঁ, বেশিরভাগটাই দরকারি। তবে ছোট করা যায়, এবং এর একটি তথ্য পুরোনো হয়ে গেছে।**

ভালো comment বলে **কেন** এবং **কোন নিয়ম (invariant) কখনো ভাঙা যাবে না**। code পড়ে এগুলো বোঝা যায় না। এই docstring এ তিনটি নিয়ম আছে, যা না জানলে ভবিষ্যতে কেউ সহজেই bug তৈরি করবে:
1. Redis এ শুধু একটি *pointer* থাকে, আসল তথ্যের উৎস DB (Redis এর data কে সত্য ধরা যাবে না)।
2. প্রতিবার cache hit হলে আবার যাচাই হয় (deleted submission বা পুরোনো version এর ফলাফল কখনো serve করা যাবে না)।
3. hit হলেও `context.submission_id` বদলায় না (একজনের submission আরেকজনকে দেওয়া যাবে না)।

তবে দুটি সমস্যা আছে:
* "(owner, photo-card image, **OCR record**)" অংশটি পুরোনো। OCR এখন আর নেই, ওটা এখন `photocard_extractions`।
* identity তে কোন কোন field থাকে তার পুরো তালিকা `hashing.compute_claim_hash` এ আছে। এখানে আবার লিখলে দুই জায়গা আলাদা হয়ে যাওয়ার ঝুঁকি থাকে, তাই এখানে শুধু reference দিলেই চলে।

**প্রস্তাবিত ছোট রূপ:**

```python
class CacheLookupStage:
    """S02: reuse an earlier identical, complete verification.

    Invariants:
    * Redis stores only a pointer; the DB row is authoritative and is
      re-validated on every hit (see `reuse.result_is_reusable`).
    * A hit never changes `context.submission_id`; the service layer copies
      the result onto the caller's own submission (`ResultReuseService`).
    Identity = `hashing.compute_claim_hash`.
    """
```

### 7.2 Comment রাখার নিয়ম (codebase জুড়ে প্রয়োগের জন্য)

| ধরন | উদাহরণ | কী করবেন |
|---|---|---|
| **Invariant বা "কেন"** | S02 এর নিয়ম, `jobs.py` তে durability এর ব্যাখ্যা, `s05` এর Cloudflare এর জন্য অপেক্ষার কারণ, `material_differences` এর rule গুলোর তালিকা, `headline_comparison` এর decision procedure | **রাখুন** (প্রয়োজনে ছোট করুন) |
| **Change-log বা ইতিহাস** ("Previously…", "Root cause of the defect this replaces…", "Migrated from…") | `nlp/nli_service.py` (৩০ লাইন জুড়ে আগের model এর গল্প), `analysis/keywords.py` (প্রথম ১৮ লাইন), `verification/verdict_compat.py`, `nlp/ner_service.py` ("the earlier `text[:1000]` truncation…"), `s06` ("Previously the date was only looked for…"), `articles/schemas.py` ("Migrated from: app/schemas/article.py"), `shared/utils/article_url_heuristics.py` এর "Why this exists" (পুরোনো `NOT_FOUND_IN_CLAIMED_SOURCE` এর উল্লেখ), `config.py` এর `nli_model_name` এর description | **সরান**। এগুলো commit message, PR বা `docs/` এ থাকা উচিত। code এ শুধু এখনকার অবস্থা লিখুন। |
| **ভুল বা পুরোনো (stale)** | নিচের তালিকা | **ঠিক করুন**। ভুল comment না থাকার চেয়েও খারাপ। |
| **Code যা নিজেই বলে, সেটা আবার লেখা** | `"""Return True if the exception is…"""` ধরনের | সরান |
| **Module path header** (`"""app/features/nlp/nli_service.py\n=====…"""`) | `nli_service.py`, `ner_service.py`, `orchestrator.py`, `factory.py`, `articles/schemas.py`, `article_url_heuristics.py`, `retry.py` | সরান। file path টি file নিজেই বলে দেয়। |

### 7.3 ভুল বা পুরোনো comment (ঠিক করতে হবে)

| জায়গা | কী ভুল |
|---|---|
| `photocard/storage_service.py` এর module docstring | "Upload failures are reported … because **OCR works from the bytes already in memory** … should not block verification"। এখন OCR নেই, এবং upload ব্যর্থ হলে submission গ্রহণই করা হয় না (`ImageStorageUnavailableError`)। |
| `s11_date_verification.py` এর docstring | "**A date printed on a photo card is never used here**"। এটি ভুল। photo card এর ছাপা তারিখটিই `submission.published_date` হয় (`photocard/service.py:215`), এবং S11 সেটাই তুলনা করে। |
| `verification/reuse.py` ও `s02_cache_lookup.py` | "OCR record" |
| `multimodal/models.py` এর docstring | "replacing `MultimodalPrediction` **above**, which is now frozen/legacy"। ঐ class এখন আর নেই। |
| `main.py` ও `verification/router.py` এর description | "**12-stage** pipeline"। আসলে stage ১৩টি (S01–S13)। |
| `sources/models.py` এর `js_rendered` | "requires Playwright"। field টি কোথাও পড়া হয় না। Playwright সব source এর জন্য স্বয়ংক্রিয়ভাবে চলে। |
| `s01_normalizer.py` এর comment (লাইন ৬০–৬৩) | `PhotoCardService.verify` এর উল্লেখ আছে, কিন্তু এই নামে এখন কোনো method নেই (এখন `process_submission`) |
| `config.py` এর `RedisSettings.ttl_embedding` | "LaBSE embedding vectors"। মান টি ব্যবহারই হয় না। |
| `verification/models.py` এর `final_*` column comment | "Written only by ExpertReviewService"। এখন কেউ লেখে না। |
| `retry.py` | path ও উদাহরণ (`call_brave_api`) ভুল। file টিই delete করার কথা। |
| `escalation.py`, `overall_verdict.py`, `public_votes.py` | file এর শুরুতে দুটি ফাঁকা লাইন। সম্ভবত module docstring মুছে ফেলার পরে থেকে গেছে। প্রতিটির জন্য এক লাইনের docstring লিখুন। |

---

## 8. অনুচিত default value

### 8.1 `model_config = {"json_schema_extra": {"example": {...}}}` সম্পর্কে

একটা technical স্পষ্টীকরণ: `json_schema_extra` এর `example` **runtime default নয়**। এটি শুধু OpenAPI/Swagger documentation এ দেখানো হয়। কোনো field এর মান এখান থেকে আসে না, তাই এটি business logic এ কোনো ভুল মান ঢোকায় না।

তবুও আপনার মত (এগুলো এভাবে রাখা উচিত নয়) software engineering এর দিক থেকে যুক্তিসঙ্গত, কারণ:

1. **পুরোনো ও বিভ্রান্তিকর data:** `articles/schemas.py` এর example এ `"search_provider": "google_rss"` আছে, যে provider এখন project এ নেই। তারিখ `2024-03-15`, URL `/article/12345` ইত্যাদি বানানো।
2. **Internal DTO এর example এর কোনো দরকার নেই:** `ExtractedContentSchema`, `CandidateArticleSchema`, `ArticleExtractionResult`, `NLIScoresSchema` কোনো API এ input বা output হিসেবে যায় না, অথচ এদের example আছে।
3. **Schema file অপ্রয়োজনে বড় হয় এবং duplicate তৈরি হয়:** `sources/schemas.py` তে তিনটি আলাদা example block আছে।
4. **Documentation আর code এ আলাদা হয়ে যায়:** `VerificationResponse` এর example এ শুধু কিছু field আছে, নতুন field গুলো নেই।

**পরামর্শ (আচরণ বদলাবে না):**
* internal DTO থেকে `json_schema_extra` পুরোপুরি **সরান**।
* public request/response schema এ example দরকার হলে field level এ `Field(examples=[...])` দিন (Pydantic v2 এর নিয়ম মেনে), অথবা router এ `openapi_examples=` দিন। তাহলে example টি endpoint এর পাশে থাকে।
* example data বাস্তবসম্মত ও চালু code এর সাথে সামঞ্জস্যপূর্ণ রাখুন (যেমন provider `internal_site`/`py_google_news`)। চাইলে একটি test লিখুন যা প্রতিটি example কে `Model.model_validate(example)` দিয়ে যাচাই করে।

### 8.2 যে default গুলো আসলেই সমস্যা তৈরি করে (runtime এ প্রভাব আছে)

| জায়গা | Default | সমস্যা | পরামর্শ |
|---|---|---|---|
| `AuthSettings.secret_key` | `"CHANGE_ME_IN_PRODUCTION_…"` | এই মান এখন **চালু অবস্থায় ব্যবহার হচ্ছে** (section 1.1) | required করুন, default রাখবেন না |
| `DatabaseSettings.password` = `"postgres"`, `MinioSettings.access_key/secret_key` = `"minioadmin"` | credential এর default | config এ কিছু বাদ পড়লেও app নীরবে চালু হয়ে যায় | required করুন (dev এর মান শুধু `.env.example` এ থাকবে) |
| `AppSettings.cors_origins` | `["*"]` | security (section 1.3) | `[]` |
| `GeminiSettings.all_api_keys` | code এ `"your-gemini-api-key-here"` placeholder string টি বাদ দেওয়ার logic hardcoded | config এর placeholder এর তথ্য code এ ঢুকে গেছে | example এ মান খালি রাখুন এবং এই check সরান |
| `MultimodalSettings.model_dir` | `~/.cache/...` | `.env` আর বাস্তব path আলাদা | default না রেখে required করুন |
| `SearchSettings.top_k_candidates` | 15 (example এ 5) | section 4.3 | একই মান রাখুন |
| `users/router.py: SubmissionSummary.submission_type` | `= SubmissionType.SOURCE_BASED` | যেকোনো submission এর type সবসময় জানা থাকে, তাই default অর্থহীন। ভুলবশত বাদ পড়লে ভুল মান দেখাবে। | required করুন |
| `expert_review/service.py:get_history` | submission না পেলে `SubmissionType.SOURCE_BASED` বসায় | মিথ্যা data | `None` রাখুন এবং schema কে `SubmissionType \| None` করুন |
| `ExpertStatsResponse.activation_threshold` | `= 10` | আসল মান DB এর `voting_config` এ থাকে, এই 10 তার duplicate | required করুন |
| `ExpertQueueItemResponse.decision_mode` | `= "EXPERT_VOTE"` (string) | magic string | `DecisionMode` enum বানান, এবং required করুন |
| `DashboardActivity.kind`, `PublicVote.reviewer_role`, `PublicVotingDetails.decided_by` | free `str` | `Literal`/enum হওয়া উচিত | enum বানান |
| `HealthResponse.version` | `= "1.0.0"` | hardcoded | settings থেকে নিন |
| `VerificationResponse.confidence_meaning` | ৫ লাইনের একটি documentation string | প্রতিটি response এ একই লেখা যায়, এটা data নয়, documentation | `Field(description=...)` এ সরান। API contract বদলানোর অনুমতি থাকলে তবেই field টি সরান। |
| `VerificationResponse.was_overridden` | `False`, deprecated | dead field | API contract অনুযায়ী পরের version এ সরান |
| `presenter.py:182` | প্রতিটি article এর জন্য `search_provider=SearchProvider.INTERNAL_SITE` hardcoded | **মিথ্যা data**। এই তথ্য `RetrievedArticle` এ সংরক্ষিতই হয় না। | `RetrievedArticle` এ provider persist করুন, অথবা schema তে `search_provider` কে `Optional` করে `None` দিন |
| `s06_article_extractor.py:146` | candidate না পেলে provider `SearchProvider.GOOGLE_RSS` | অস্তিত্বহীন provider | `None` দিন |
| `s13_result_persistence.py:287` | `search_provider_used or SearchProvider.PY_GOOGLE_NEWS` | ভুল fallback | `None` দিন (column nullable করতে হবে) |
| `ExpertReview.credibility_weight` (model) | `default=0.5` | সব জায়গায় মান explicitly দেওয়া হয়। 0.5 হলো পুরোনো "initial credibility" এর অবশিষ্ট, বর্তমান neutral weight 1.0 এর সাথে সাংঘর্ষিক। | default সরান |
| `ExpertReview.status` | `"pending"` (string) | magic string, `"finalized"` এর সাথে | `ReviewStatus` enum বানান |
| `VotingConfigRepository.get_or_create` | `VotingConfig(min_expert_votes=3)` | model এও default 3 আছে, তাই duplicate | parameter ছাড়া call করুন |
| `ExpertProfileRepository.get_or_create(area_of_expertise="General")` এবং `AdminService` এর `or "General"` | duplicate default | | একটি constant রাখুন |
| `VerificationJob.max_attempts=3` (model) এবং `enqueue(... max_attempts=3)` | duplicate | | `JobSettings.max_attempts` এ রাখুন |
| `reuse.py:materialize` | `confidence or 0.0`, `reasoning or ""` | source এ None থাকলে copy তে মিথ্যা 0 বসে যায় | যেমন আছে তেমনই copy করুন |
| `CacheService.set_raw(ttl=3600)` | magic number | | caller কে ttl দিতে বাধ্য করুন |
| `PhotoCardResultResponse.claim_scope = HEADLINE_ONLY` | service সবসময় এই মান explicitly দেয় | | default সরান অথবা `Literal[ClaimScope.HEADLINE_ONLY]` ব্যবহার করুন |
| `AdminStatsResponse.escalated_claims = 0` | service সবসময় মান দেয় | | default সরান |
| `MultimodalSettings` (`num_classes`, `dropout`, `img_size`, `max_seq_length`) | `config.json` এর duplicate | training config এর সাথে আলাদা হয়ে যেতে পারে | একটি উৎস রাখুন |

---

## 9. এক file এ একাধিক দায়িত্ব বা class: ভাগ করার পরামর্শ

### 9.1 Router এর মধ্যে schema, query ও business logic ("fat router")

| File | ভেতরে যা আছে | যেভাবে ভাগ করবেন |
|---|---|---|
| `features/dashboard/router.py` (353 লাইন) | ৫টি Pydantic schema, raw SQLAlchemy query, ১০টি আলাদা `COUNT` query (একটি `GROUP BY` দিয়েই হয়), প্রতিটি item এর জন্য আলাদা query করার N+1 loop, presigned URL তৈরি, presentation mapping | `dashboard/schemas.py`, `dashboard/repository.py` (read model: stats ও explorer query), `dashboard/service.py` (mapping + image URL), router এ শুধু endpoint। N+1 এর সমাধান: `MultimodalAnalysis`, `VerificationResult`, `PhotocardExtraction` একটি query তে `IN (...)` দিয়ে আনুন। |
| `features/users/router.py` (263 লাইন) | ৪টি schema, SQL, প্রতিটি submission এ ৪–৫টি query (N+1), presenter logic, method এর ভেতরে import, `HTTPException` (domain error এর বদলে) | `users/schemas.py`, `users/service.py` (`MySubmissionsService`), query গুলো `SubmissionRepository` এ। expert হলে profile edit বন্ধ করার নিয়মটি service এ রাখুন এবং `PermissionDeniedError` দিন। |
| `features/notifications/router.py` | schema + SQL | `notifications/schemas.py` + `NotificationRepository` (list, count_unread, mark_read, mark_all_read) |
| `features/health/router.py` | schema + DB/Redis check (function এর ভেতরে import) | `health/schemas.py` + `HealthService`। `db/engine.check_db_connection()` আগে থেকেই আছে, সেটা ব্যবহার করুন। |
| `features/expert_review/router.py:get_credibility` | credibility score এর হিসাব router এ | `ExpertReviewService.get_credibility()` এ সরান |
| `features/multimodal/router.py` | ছবি validation, `_to_detail` mapping, প্রতিটি item এ submission load (N+1), `BanglaFactGuardError` কে `HTTPException` এ রূপান্তর (global handler থাকায় এটা অপ্রয়োজনীয়) | validation কে `shared/uploads.py:validate_image_upload()` এ, mapping কে service/presenter এ। error conversion সরিয়ে দিন। |
| `features/sources/router.py`, `verification/router.py`, `photocard/router.py`, `submissions/router.py` | domain exception ধরে আবার `HTTPException` এ রূপান্তর | global `exception_handlers.py` আগে থেকেই এই কাজ করে। তবে response এর আকার আলাদা (`{"detail": {...}}` বনাম `{"error":…}`)। আচরণ একই রাখতে চাইলে প্রথমে frontend এর error parsing মিলিয়ে নিন, তারপর একটি পদ্ধতিতে আনুন। |

### 9.2 একাধিক feature এর class এক file এ

| File | Class গুলো | প্রস্তাব |
|---|---|---|
| `features/submissions/models.py` | `Submission`, `SourceEvidenceQuery`, `RetrievedArticle`, `PhotocardExtraction` | `PhotocardExtraction` কে `photocard/models.py` এ। `RetrievedArticle` ও `SourceEvidenceQuery` কে `verification/evidence/models.py` এ। `submissions/models.py` এ থাকবে শুধু `Submission`। (table এর নাম একই থাকবে, migration লাগবে না) |
| `features/submissions/repository.py` (491 লাইন) | `SubmissionRepository` (Fact Explorer এর জটিল search সহ), `SourceEvidenceQueryRepository`, `RetrievedArticleRepository`, `PhotocardExtractionRepository` | model এর মতোই ভাগ করুন। Explorer search কে `dashboard/repository.py` তে নিন (এটি dashboard এর read model)। |
| `features/verification/models.py` | `VerificationResult`, `VerificationJob` | `verification/jobs/models.py` তে `VerificationJob` |
| `features/expert_review/models.py` | `ExpertProfile`, `CredibilityWeightTier`, `ExpertReview`, `VotingConfig` | একসাথে রাখা যায়। চাইলে `voting_policy` (tier + config) আলাদা sub-module এ রাখুন। |
| `core/constants.py` | ১৮টি enum, ভিন্ন ভিন্ন feature এর | প্রতিটি enum তার feature এ নিন (section 13) |
| `core/config.py` (597 লাইন, ১৩টি settings class) | | একটি `core/config/` package বানান: `database.py`, `redis.py`, `ml.py`, `auth.py`, … এবং `__init__.py` থেকে `get_settings` export করুন |

### 9.3 এক class বা file এ অনেক দায়িত্ব (SRP লঙ্ঘন)

| File | দায়িত্বগুলো | ভাগ |
|---|---|---|
| `photocard/gemini_image_extractor.py` (462 লাইন) | (১) prompt text, (২) response JSON schema, (৩) response model ও validation, (৪) key rotation pool (process-wide global state), (৫) HTTP client ও retry/batch loop, (৬) MIME type বের করা, (৭) quota header parse | `photocard/extraction/gemini/` package: `prompt.py`, `schema.py` (`GeminiPhotocardFields`, `FieldStatus`, `SourceIdentification`), `key_pool.py` (`GeminiKeyPool`), `client.py` (`GeminiClient.extract()`), `errors.py` (`AttemptFailed`)। এখানকার `SourceStatus` enum এর নাম core এর `SourceStatus` এর সাথে মিলে যায়, তাই এর নাম `SourceIdentificationStatus` করুন। |
| `s05_evidence_retrieval.py` | HTTP fetch, per-domain rate limit, bot-wall/JS-shell detection, Playwright browser চালানো, Windows event loop hack, redirect allow-list | `shared/http/page_fetcher.py` এ `HttpPageFetcher` ও `BrowserPageFetcher` (একটি `PageFetcher` Protocol মেনে), `html_signals.py` (`is_bot_wall`, `is_shell_html`)। stage শুধু orchestration করবে। PyGoogleNews client ও একই `BrowserPageFetcher` ব্যবহার করবে। |
| `s06_article_extractor.py` (566 লাইন) | ৬টি extraction strategy এক method এ (~180 লাইন), date বের করা, title পরিষ্কার করা, selector এর health ট্র্যাক করা | **Chain of Responsibility / Strategy:** `ArticleExtractor` Protocol, এবং `SourceSelectorExtractor`, `JsonLdExtractor`, `TrafilaturaExtractor`, `ReadabilityExtractor`, `Bs4HeuristicExtractor`, `OpenGraphExtractor`। আলাদা `PublicationDateFinder` থাকবে। ক্রম ঠিক এখনকার মতো রাখলে আচরণ একই থাকবে। |
| `s13_result_persistence.py` | submission তৈরি বা update, article persist, result upsert, search query persist, status বদল, Redis pointer লেখা, notification পাঠানো, `users.total_submissions` বাড়ানো | stage টি একটি `VerificationResultWriter` (application service) কে delegate করবে। notification ও cache pointer এর জন্য domain event বা আলাদা collaborator রাখুন (`ResultNotifier`, `ClaimPointerCache`)। |
| `verification/jobs.py` | `JobDeps`, `execute_job` (`if kind == …` chain), `_Lane`, `VerificationJobWorker` | **Strategy / registry:** `JobHandler` Protocol, এবং `SourceBasedJobHandler`, `PhotoCardJobHandler`, `MultimodalJobHandler`। `JOB_HANDLERS: dict[JobKind, JobHandler]` থেকে handler বেছে নিন। নতুন ধরনের job এলে নতুন class যোগ করলেই হবে, worker বদলাতে হবে না (Open/Closed)। |
| `expert_review/service.py` (804 লাইন) | queue তৈরি (SQL সহ), vote, admin decision, weight হিসাব, finalize/escalate, profile update, history, stats, presentation | `expert_review/voting/` এ `VoteTally` (`_tally`, `_evaluate`), `ReviewLimitPolicy` (`review_limits_exceeded`), `WeightResolver`; `ExpertQueueService` (read side); `VotingService` (write side); `ExpertQueuePresenter`। |
| `admin/service.py` | expert CRUD, platform stats (SQL), tier CRUD ও validation, voting config, credibility score আবার হিসাব (raw SQL `UPDATE`) | `AdminExpertService`, `CredibilityTierService` (+ `TierRangeValidator`), `VotingConfigService`। stats কে `dashboard`/`admin` এর repository তে নিন। |
| `photocard/service.py` | accept, process, presentation (`_ATTEMPT_MESSAGES`, `extraction_failures`) | presentation অংশ `photocard/presenter.py` তে |
| `notifications/delivery.py` | reconcile query, notification তৈরি, email পাঠানো, worker loop | `ResultDeliveryRepository` + `ResultDeliveryService` + worker। email ও delivery এর status (`'pending'`, `'sent'`, `'skipped'`, `'not_applicable'`) ও stage (`'preliminary'`, `'final'`) এর জন্য enum বানান। |

---

## 10. Duplicate code (DRY লঙ্ঘন)

| কী duplicate | কোথায় কোথায় | কী করবেন |
|---|---|---|
| `_sha256()` | `auth/repository.py`, `auth/security.py`, `auth/service.py`, এবং `shared/utils/hashing.sha256_hex` | একটিই রাখুন (`hashing.sha256_hex`) |
| দুটি MinIO storage service (`MultimodalStorageService`, `PhotoCardStorageService`) | প্রায় একই code, পার্থক্য শুধু prefix ও error এর ধরনে | `shared/storage/object_storage.py` তে একটি `ObjectStorage` class, যা prefix নেবে (`ObjectStorage(prefix="photocard")`) |
| ছবির content-type allow-list ও size validation | `multimodal/router.py`, `photocard/router.py` (সীমা ১০ MB দুই জায়গায়, একটিতে config থেকে, অন্যটিতে hardcoded) | `shared/uploads.py` |
| Browser এর মতো HTTP header ও User-Agent | `s05`, `internal_site_client.py`, `pygooglenews_client.py` | `shared/http/headers.py` |
| Playwright boilerplate (Windows এ thread + ProactorEventLoop) | `s05`, `pygooglenews_client.py` | `BrowserPageFetcher` |
| URL থেকে tracking parameter বাদ দেওয়া | `s04._STRIP_PARAMS` ও `hashing._TRACKING_PARAMS` (**দুটি আলাদা set!**), `pygooglenews._strip_challenge_params` | একটি `shared/utils/urls.py:canonicalize_url()`। **সাবধান:** set দুটি আলাদা, তাই এক করলে hash বদলে যেতে পারে। আচরণ একই রাখতে দুটি নাম দিয়ে (`DEDUP_STRIP_PARAMS`, `HASH_STRIP_PARAMS`) আলাদাই রাখুন, শুধু এক file এ আনুন। |
| Bangla digit এর map | `bangla_normalizer`, `dates.py`, `card_date.py`, `s06`, `material_differences` | `shared/text/bangla.py` |
| Bangla মাসের নাম | `dates.py`, `card_date.py`, `s06`, `material_differences._DATE_WORDS` | `shared/text/bangla_calendar.py` |
| Stopword তালিকা | `analysis/text.STOPWORDS`, `keyword_extractor.BANGLA_STOPWORDS` (**আলাদা তালিকা**) | এক file এ রাখুন। তালিকা দুটি আলাদা বলে মান একই রাখতে হবে, নাহলে ফলাফল বদলাবে। |
| Negation word ও fused-negation regex | `analysis/text.py`, `material_differences.py` (দুটি regex সামান্য আলাদা) | উপরের মতো |
| Claim scope বের করা | `verification/service.claim_scope_for`, `pipeline/context.build_context`, `presenter.resolve_scope` | `ClaimScope.from_body(body)` (classmethod) |
| `users.total_submissions` বাড়ানো | `multimodal/service.py`, `s13_result_persistence.py` | `UserRepository.increment_submission_count()` |
| "previous result reused" notification | `verification/service.py` এ দুইবার, `photocard/service.py` এ একবার | `ResultNotifier.notify_reused(target)` |
| Credibility বা accuracy এর হিসাব | `admin/service.update_voting_config` (SQL), `expert_review/router.get_credibility`, `service.get_stats`, `service._update_expert_profiles` | `ExpertProfile.credibility(activation_threshold)` (domain method) |
| Explorer, my-submissions, expert queue এ result + multimodal + image URL একসাথে করা | `dashboard/router`, `users/router`, `expert_review/service` | `SubmissionCardAssembler` |
| Image transform ও decode | `multimodal/pipeline/embedding_extractor.py`, `inference_engine.py` | `multimodal/pipeline/preprocessing.py` |
| Multimodal inference এ backbone দুইবার চালানো | extractor একবার text/image backbone চালায়, তারপর inference engine **আবার** চালায় | engine কে embedding গ্রহণ করতে দিন (`classifier(img_feats, text_feats)`)। ফলাফল একই থাকবে, শুধু দ্বিগুণ CPU খরচ বাঁচবে। |
| Search query থেকে `site:` সরানো | `s03`, `s04._adapt_query`, `internal_site_client._build_keyword_query`, `pygooglenews` | একটি helper |
| Domain normalize করা (`www.` বাদ দেওয়া) | `domains._host`, `bangla_normalizer.extract_canonical_domain`, `s06`, `s07._source_domain_bonus`, `internal_site_client` | `shared/utils/domains.py` তে এক জায়গায় |
| `Metric` এর মতো দেখতে type | `analysis/decisions.Metric`, `schemas.MetricDetail`, `body_similarity.MetricResult`, `schemas.BodySimilarityMetric` | domain value object একটি, এবং schema গুলো `from_attributes` দিয়ে তৈরি |
| LaBSE model এর নাম | `embedding_service`, `body_similarity.SEMANTIC_MODEL`, schema description | config থেকে নিন |

---

## 11. OOP ও SOLID নীতি অনুযায়ী redesign

### 11.1 Single Responsibility (SRP)
উদাহরণ section 9.3 এ আছে। মূল কথা: **router শুধু HTTP সামলাবে, service business rule রাখবে, repository শুধু DB query করবে, presenter শুধু response বানাবে।** এখন বেশ কিছু router নিজেই DB query করে, আর service presentation string তৈরি করে।

### 11.2 Open/Closed (OCP)
* **Job এর ধরন:** `execute_job` এর `if kind == "MULTIMODAL" … elif "PHOTO_CARD" … else` chain এর জায়গায় handler registry (section 9.3)।
* **Material difference rule:** `find_material_differences()` একটি বড় function। এর জায়গায় `MaterialDifferenceRule` Protocol (`def find(claim, source, ctx) -> list[MaterialDifference]`) এবং `NumbersRule`, `DateRule`, `NegationRule`, `ModalityRule`, `ScopeRule`, `RoleSwapRule`, `AttributionRule`, `DenialRule`, `EntityRule`। নতুন rule যোগ করতে এখনকার code বদলাতে হবে না। ক্রম একই রাখলে output একই থাকবে।
* **Article extractor:** Chain of Responsibility (section 9.3)।
* **Search provider:** S04 এ এখন `if provider_enum == INTERNAL_SITE: kwargs["source_config"]=…` এর মতো বিশেষ ব্যবস্থা আছে। এর বদলে একটি `SearchProvider` interface দিন (নিচে দেখুন)।

### 11.3 Liskov Substitution ও Interface Segregation (LSP/ISP)
* দুটি search client এর `search_entries` এর signature আলাদা (`InternalSiteSearchClient` একটি অতিরিক্ত `source_config` নেয়)। তাই S04 কে client এর ধরন দেখে আলাদা আচরণ করতে হয়। সমাধান:

```python
class SearchQuery(BaseModel):          # value object
    text: str
    domain: str
    published_date: date | None
    source: SourceConfig               # typed, not dict

class NewsSearchProvider(Protocol):
    provider: SearchProvider
    def is_configured_for(self, source: SourceConfig) -> bool: ...
    async def search(self, q: SearchQuery) -> list[SearchHit]: ...
```

  এভাবে "not configured" এর সিদ্ধান্ত হবে `is_configured_for()` দিয়ে, error message এর string মিলিয়ে (`"not configured" in err_str`) নয়।
* `PipelineStage` Protocol ভালো, সব stage এটি মানে। তবে S05 ও S06 এর মধ্যে তথ্য যায় `context._raw_html_cache` দিয়ে, যা dataclass এ ঘোষিত নয় (একটি **লুকানো contract**)। এটিকে field হিসেবে ঘোষণা করুন (`fetched_pages: dict[str, str]`)।

### 11.4 Dependency Inversion (DIP)
* `AuthService` নিজে `EmailService()` তৈরি করে। `MultimodalPredictionService` constructor এর ভেতরে repository, extractor ও engine তৈরি করে। `S07` নিজে `CrossEncoderReranker()` বানায়। `get_photocard_storage` প্রয়োজন হলে নিজেই storage তৈরি করে `app.state` এ রাখে। **এই সব dependency constructor দিয়ে inject করুন** (FastAPI `Depends` বা একটি ছোট composition root, যেমন `app/bootstrap.py`)।
* `get_current_user` নিজে `AsyncSessionLocal()` খোলে। এর বদলে `Depends(get_async_session)` + `UserRepository` ব্যবহার করুন।
* প্রায় ২৪টি module import এর সময় `_SETTINGS = get_settings()` চালায়। এতে test এ setting override করা কঠিন হয়। constructor এ settings inject করুন।

### 11.5 Encapsulation ও Law of Demeter
* `escalation.py` বাইরে থেকে `svc._submissions.get_by_id_locked()` ও `svc._finalize_or_escalate()` (private member) call করে। `ExpertReviewService` এ একটি public method দিন: `reevaluate(submission_id, now)`।
* Router গুলো service এর repository সরাসরি ব্যবহার করে (`service.submission_repo.get_by_id_or_none`) (`verification/router.py`, `photocard/router.py`)। service এ `get_visible_result(id, viewer)` দিন।
* `auth/router.py` service এর private `_to_me_response` import করে। `admin/service.py` import করে `auth.service._validate_password_strength`। এগুলোকে public করুন (`PasswordPolicy.validate()`)।
* Service গুলো `repo.session` দিয়ে সরাসরি SQL চালায় (`ExpertReviewService._session = review_repo.session`, `AdminService`, `AuthService.refresh`)। এই কাজগুলো repository method এ নিন।
* `passages.py` ও `material_differences.py` অন্য module এর private `_evidence_keys` import করে। একে public করুন (`evidence_keys`)।

### 11.6 ডেটার একক উৎস (Single Source of Truth)
* **Source এর নাম ও alias:** এখন তিনটি জায়গায় আছে: DB এর `verified_sources.aliases`, `core/constants.KNOWN_SOURCE_ALIASES`, আর `s06._TITLE_SUFFIX_RE`। এদের মধ্যে DB ই আসল উৎস। resolution এর ক্রম এখন *static map → DB*। deactivate করা বা DB তে নেই এমন outlet ও resolve হয়ে যায়। পরামর্শ: DB alias এর উপর ভিত্তি করে একটি in-memory `SourceCatalog` (TTL cache) বানান, এবং static map ও regex সরিয়ে দিন।
  **সতর্কতা:** এতে আচরণ বদলাবে। যেমন `bdnews24` এর মতো যে source গুলো DB তে নেই, সেগুলোর claim আর গ্রহণ করা হবে না। পরিবর্তনটি ইচ্ছাকৃত হলে তবেই করুন। `source_registry.py` এই পরিবর্তনের অংশ নয়।
* **Version:** section 4.1 দেখুন।
* **Model এর নাম:** section 1.4 দেখুন।

### 11.7 Magic string এর বদলে enum বা value object
| String | প্রস্তাবিত enum |
|---|---|
| `"user"`, `"expert"`, `"admin"` (৩০টির বেশি জায়গায়) | `UserRole(str, Enum)`, এবং `require_role(UserRole.ADMIN)` |
| `"QUEUED"`, `"EXTRACTING"`, `"VERIFYING"`, `"DONE"`, `"FAILED"` | বিদ্যমান `JobPhase` |
| Job এর `kind` (`"SOURCE_BASED"`, `"PHOTO_CARD"`, `"MULTIMODAL"`) | `SubmissionType` আগে থেকেই আছে, সেটাই ব্যবহার করুন |
| Job এর `status` (`"QUEUED"`, `"RUNNING"`, `"DONE"`, `"FAILED"`) | `JobStatus` |
| Expert review এর status (`"pending"`, `"finalized"`) | `ReviewStatus` |
| Photocard extraction এর status ও failure code | `ExtractionStatus`, `ExtractionFailureCode` |
| Gemini attempt এর outcome | `AttemptOutcome` |
| Correspondence level (`"STRONG"`, `"PLAUSIBLE"`, `"NONE"`, `"UNKNOWN"`) | `CorrespondenceLevel` (এখন `_LEVEL_RANK` dict দিয়ে র‍্যাঙ্ক করা হয়) |
| Headline comparison এর `basis` | `ComparisonBasis` |
| Material difference এর `kind`, entity match এর status | `DifferenceKind`, `EntityMatchStatus` |
| Notification type (`"VERIFICATION_COMPLETE"` ইত্যাদি) | `NotificationType` |
| Result delivery এর stage ও email status | `DeliveryStage`, `EmailStatus` |
| `source_config: dict` | typed `SourceConfig` dataclass (`allowed_domains`, `selectors`, `internal_search_url`, `article_url_patterns`) |
| `headline_check_status`, `body_comparison_status`, `claim_scope` column (এখন String) | ORM এ `Enum(..., native_enum=False)` দিয়ে map করুন। এতে DB পরিবর্তন লাগবে না, Python এ enum পাওয়া যাবে। |

### 11.8 Rich domain model (Anemic model থেকে বের হওয়া)
* `Submission` এর state transition (`PENDING → PROCESSING → EXPERT_REVIEW → FINALIZED/ESCALATED/FAILED`) এখন repository তে update query হিসেবে ছড়িয়ে আছে। একটি `SubmissionLifecycle` (state machine) রাখুন, যাতে অবৈধ transition এ exception আসে।
* `VerificationResult.is_reusable()` (এখন `reuse.result_is_reusable`), `ExpertProfile.credibility()`, `VotingConfig.limits_exceeded()`: এই নিয়মগুলো সংশ্লিষ্ট object এর method হিসেবে রাখুন।

---

## 12. Global state, lifecycle ও transaction boundary

### 12.1 Import এর সময় তৈরি হওয়া global ও class-level singleton
| জিনিস | কোথায় | সমস্যা |
|---|---|---|
| ৮টি `ThreadPoolExecutor` | `multimodal/storage_service`, `photocard/storage_service`, `embedding_extractor`, `inference_engine`, `model_loader`, `embedding_service`, `ner_service`, `nli_service` | import করলেই thread pool তৈরি হয়, কিন্তু shutdown এ বন্ধ হয় না |
| Class attribute এ model রাখা (`EmbeddingService._model`, `NERService._pipeline`, `NLIService._pipeline`, `MultimodalModelLoader._loaded/_lock`, `CrossEncoderReranker._model`) | — | লুকানো global state। `MultimodalModelLoader._loaded` class এর উপর বসে, কিন্তু weight গুলো রাখা হয় instance এ। ফলে দ্বিতীয় একটি instance বানালে `is_loaded=True` দেখায়, অথচ property পড়লে `ModelNotLoadedError` আসে। |
| `_POOLS` (Gemini key pool) | `gemini_image_extractor.py` | process-wide mutable dict |
| `_async_engine` | `db/engine.py` | import এর সময় engine তৈরি হয় |

**পরামর্শ:** এগুলো `lifespan` এ তৈরি করে `app.state` বা একটি `Container` এ রাখুন, shutdown এ `executor.shutdown()` ও `engine.dispose()` চালান। Model গুলো instance attribute হিসেবে রাখুন, এবং একটি instance তৈরি করে সবখানে share করুন। singleton রাখার দায়িত্ব DI এর, class এর নয়।

### 12.2 Transaction boundary এলোমেলো
* `shared/dependencies.get_async_session` request শেষ হলে **commit** করে। অথচ `VerificationService.register_claim`, `PhotoCardService.accept_upload`, `MultimodalPredictionService.accept_upload` নিজেরাও `session.commit()` call করে। ফলে একই request এ commit দুইবার হয়, এবং কোন অংশ atomic তা পরিষ্কার নয়।
* `BaseRepository.create()` এ `IntegrityError` হলে `session.rollback()` call করে। এতে caller এর পুরো transaction বাতিল হয়ে যায়, যা caller জানে না।
* **পরামর্শ:** একটি Unit of Work pattern আনুন: application service এর একটি use-case এ একবার commit হবে। repository কখনো commit বা rollback করবে না। job worker নিজের transaction নিজে চালাবে (এখন যেমন করে)।

---

## 13. প্রস্তাবিত Package-by-Feature structure

নীতি:
* **একটি feature = একটি package**, যার ভেতরে `router`, `schemas`, `service`, `repository`, `models`, `exceptions`, `enums` থাকবে।
* Feature এর বাইরে থাকবে শুধু দুই ধরনের জিনিস: সত্যিকারের shared infrastructure (DB, cache, storage, HTTP, email) আর text utility।
* `core/` এ শুধু framework এর জিনিস (config, logging, base exception, app factory)।

```
backend/
├── app/
│   ├── main.py                       # create_app() only
│   ├── bootstrap.py                  # composition root: build services, workers (from lifespan)
│   ├── core/
│   │   ├── config/                   # one module per settings group, get_settings()
│   │   ├── logging.py
│   │   ├── exceptions.py             # base errors only
│   │   ├── lifespan.py
│   │   └── platform.py               # Windows event-loop policy (one place)
│   ├── infrastructure/               # shared technical adapters (no business rules)
│   │   ├── db/ (engine.py, base_model.py, base_repository.py, unit_of_work.py, models_registry.py, migrations/)
│   │   ├── cache/redis_cache.py      # former features/cache
│   │   ├── storage/object_storage.py # one MinIO adapter, prefix per feature
│   │   ├── http/ (headers.py, page_fetcher.py, browser.py)
│   │   └── email/smtp_mailer.py
│   ├── shared/
│   │   ├── text/ (bangla.py, bangla_calendar.py, stopwords.py, cleaner.py)
│   │   ├── utils/ (hashing.py, dates.py, domains.py, urls.py, headline_preview.py, article_url_heuristics.py)
│   │   ├── uploads.py                # image validation
│   │   ├── status_labels.py
│   │   └── pagination.py
│   └── features/
│       ├── auth/        models · schemas · repository · service · router · security · password_policy · enums(UserRole)
│       ├── users/       schemas · service · router
│       ├── admin/       schemas · services/(experts, tiers, voting_config) · repository(stats, dashboard) · router
│       ├── sources/     models · schemas · repository · service · router · resolution · catalog
│       ├── submissions/ models(Submission) · repository · schemas · access · lifecycle · router
│       ├── verification/
│       │   ├── router.py · schemas.py · service.py · presenter.py · reuse.py · enums.py
│       │   ├── models.py               # VerificationResult
│       │   ├── evidence/               # RetrievedArticle, SourceEvidenceQuery, schemas (former articles/)
│       │   ├── search/                 # NewsSearchProvider protocol, internal_site.py, google_news.py
│       │   ├── extraction/             # article extractor chain, publication date finder
│       │   ├── nlp/                    # embedding, nli, ner, cross_encoder (only used here)
│       │   ├── analysis/               # existing pure logic (+ rules/ for material differences)
│       │   ├── pipeline/
│       │   │   ├── context.py · orchestrator.py · factory.py
│       │   │   ├── source_registry.py  # unchanged, as requested
│       │   │   └── stages/
│       │   └── jobs/                   # models(VerificationJob) · repository · worker · handlers/
│       ├── photocard/
│       │   ├── models.py (PhotocardExtraction) · repository · schemas · service · presenter · router
│       │   └── extraction/ (claim_extraction.py, card_date.py, gemini/{client,prompt,schema,key_pool}.py)
│       ├── multimodal/  models · repository · schemas · service · router · pipeline/(loader, architecture, preprocessing, embedding, inference)
│       ├── expert_review/ models · schemas · repository · router · services/(queue, voting) · voting/(tally, policy, weights) · escalation · public_votes
│       ├── notifications/ models · schemas · repository · service · router · delivery/(service, worker)
│       ├── dashboard/   schemas · repository(read model: stats, explorer) · service · router
│       └── health/      schemas · service · router
├── scripts/
│   ├── diagnostics/report_verification_timings.py
│   └── (bootstrap_empty_sources.py — optional, see 2B)
└── tests/  (mirror the feature tree: tests/features/verification/…)
```

এই structure এর সুবিধা:
* **High cohesion:** একটি feature এর সব কিছু এক জায়গায় থাকে। যেমন "photocard" সংক্রান্ত code এখন `submissions/models.py`, `submissions/repository.py`, `photocard/`, `verification/jobs.py` এ ছড়িয়ে আছে, নতুন structure এ সব এক package এ।
* **Low coupling:** feature গুলো একে অপরের সাথে কথা বলে public service দিয়ে। এখন `nlp` (নিচের স্তর) `verification.schemas` ও `verification.analysis` import করে, অর্থাৎ dependency উল্টো দিকে যায়। প্রস্তাবিত structure এ `nlp` থাকবে `verification` এর ভেতরে, কারণ এটি শুধু সেখানেই ব্যবহার হয়।
* `features/cache`, `features/search`, `features/nlp`, `features/articles` আসলে feature নয় (কোনো router নেই)। এগুলো infrastructure বা অন্য feature এর অংশ হিসেবে যাবে।

---

## 14. ধাপে ধাপে করার পরিকল্পনা

প্রতিটি ধাপ আলাদা PR এ করুন, এবং প্রতিবার পুরো test suite (`pytest`) পাস করতে হবে। আচরণ একই থাকছে কিনা নিশ্চিত করতে refactor শুরুর **আগে** নিচের contract test গুলো যোগ করুন:
* প্রধান endpoint গুলোর response snapshot (`/verify/{id}`, `/photocard/{id}`, `/dashboard/explorer`, `/users/me/submissions`, `/expert/queue`)।
* `compute_claim_hash`, `compute_photocard_hash`, `compute_url_hash` এর মান fixed (golden) test দিয়ে আটকে রাখুন, যাতে পুরোনো cache বা reuse ভেঙে না যায়।

| ধাপ | কাজ | ঝুঁকি |
|---|---|---|
| 0 | Security: `AUTH_SECRET_KEY`, SMTP password revoke, CORS, admin password (section 1) | কম (JWT secret বদলালে সবাইকে আবার login করতে হবে, এটা প্রত্যাশিত) |
| 1 | পরিষ্কার করা: section 2A এর file, `__pycache__`/coverage untrack, অব্যবহৃত constant/exception/settings/method/`.env` variable মুছে ফেলা | খুব কম |
| 2 | Dependency file ঠিক করা (section 1.6), `.env.example` generate করা | কম |
| 3 | Comment ঠিক করা (section 7) এবং `json_schema_extra` পরিষ্কার করা (section 8.1) | শূন্য |
| 4 | Magic string এর জায়গায় enum (section 11.7)। `str, Enum` ব্যবহার করলে JSON ও DB এর মান একই থাকে। | কম |
| 5 | Fat router ভাঙা (section 9.1) ও N+1 query ঠিক করা | মাঝারি (snapshot test দরকার) |
| 6 | File ও model নতুন জায়গায় সরানো (section 9.2, 13)। table এর নাম না বদলালে migration লাগবে না। `models_registry` update করতে হবে। | মাঝারি |
| 7 | Duplicate code এক জায়গায় আনা (section 10)। stopword, tracking-param ও negation তালিকাগুলোর মান হুবহু রাখতে হবে। | মাঝারি |
| 8 | Strategy/registry: job handler, article extractor, material difference rule, search provider (section 11.2–11.3) | মাঝারি |
| 9 | DI, lifecycle ও Unit of Work (section 11.4, 12) | বেশি, সবশেষে করুন |
| 10 | (ঐচ্ছিক, আচরণ বদলায়) `SourceCatalog` কে একমাত্র উৎস বানানো (section 11.6), অব্যবহৃত DB column সরানোর migration, অব্যবহৃত endpoint সরানো | সিদ্ধান্ত নিতে হবে |
