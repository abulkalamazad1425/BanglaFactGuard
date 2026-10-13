# BanglaFactGuard — Backend

This is the FastAPI service behind the BanglaFactGuard website and Chrome extension. It handles:

- accounts and roles;
- the verification pipeline for typed claims and photo cards;
- the multimodal (text + image) fake-news model;
- the durable background job queue;
- weighted expert voting with admin escalation;
- notifications and result emails.

The [repository README](../README.md) explains the product as a whole. This file covers how the backend is built and how to run it.

## Quick start (PowerShell, from `backend/`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium     # headless browser for JS-rendered / protected pages
if (!(Test-Path .env)) { Copy-Item .env.example .env }        # then fill in your own values
docker compose up -d                                          # Redis + MinIO only
.\.venv\Scripts\python.exe -m alembic upgrade head            # needs an existing PostgreSQL database (DB_NAME)
.\.venv\Scripts\python.exe scripts/seed_verified_sources.py   # registers the ten verified outlets
.\.venv\Scripts\python.exe run.py                             # http://127.0.0.1:8000 (auto-reload)
```

`AUTH_SECRET_KEY` (at least 32 characters) is required. The app will not start without it. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

`run.py` starts uvicorn with `reload=True` and the Windows Proactor event loop, which Playwright needs. Editing any file under `app/` restarts the process. Jobs that are running at that moment are picked up again once their heartbeat goes stale (about 120 s). API docs are at <http://localhost:8000/docs>.

**Models.**

- **Local NLP models** (LaBSE, NLI, NER and a cross-encoder) download from Hugging Face on first use.
- **Multimodal model.** `MULTIMODAL_MODEL_DIR` must contain `img_backbone.pt`, `text_backbone.pt`, `classifier.pt` and `tokenizer/`.
  - `app/features/multimodal/multimodal_model/` holds `classifier.pt`, `config.json` and `tokenizer/`.
  - Copy the two backbone files there (they are gitignored because of their size).
  - Then set `MULTIMODAL_MODEL_DIR=app/features/multimodal/multimodal_model`.
- **Skipping models during development.** Use `ML_LOAD_MODELS_ON_STARTUP=false` and `MULTIMODAL_LOAD_ON_STARTUP=false`.

## Architecture

```text
app/
|-- main.py                 create_app(): CORS, middleware, /api/v1 router, exception handlers
|-- api/                    v1 router, CorrelationID (X-Request-ID) and ProcessTime (X-Process-Time-Ms) middleware
|-- core/                   config.py (all settings), constants.py (enums, pipeline version),
|                           lifespan.py (startup/shutdown), logging.py (structlog), exceptions.py
|-- db/                     async engine/session, Alembic migrations
|-- features/<feature>/     router.py -> service.py -> repository.py -> models.py, plus schemas.py
`-- shared/                 base model/repository, DI dependencies, email service, status labels,
                            utils (Bangla normaliser, hashing, keywords, dates, domains, text cleaning)
```

| Feature | Responsibility |
| --- | --- |
| `auth` | Registration, login, JWT access/refresh tokens, password reset by emailed one-time code (OTP), password change, `require_role` |
| `users` | *My Submissions* (search, state and type filters), submission stats, profile |
| `submissions` | Submission, retrieved-article, search-query and photo-card-extraction models; type lookup; who may see what (`access.py`) |
| `verification` | Text & source service, the 13-stage pipeline, analysis (headline comparison, material differences, body similarity, decisions), result reuse, presenter (single read path), durable jobs |
| `photocard` | Image upload, Gemini extraction with key rotation, mapping the card to a claim, photo-card pipeline wiring, MinIO storage |
| `multimodal` | BanglaBERT + EfficientNet-B4 model loading, inference, embedding-based duplicate detection, MinIO storage |
| `sources` | Verified-source registry (CRUD, alias resolution) |
| `search` | Google News client (`pygooglenews`, links resolved with Playwright) and outlet-internal site search |
| `nlp` | LaBSE embedding, NLI and NER services |
| `expert_review` | Queue, votes, weighted consensus, credibility, escalation worker, public voting details |
| `admin` | Expert accounts, credibility tiers, voting configuration, admin dashboard, platform stats |
| `dashboard` | Public stats, most-claimed sources, Fact Explorer search |
| `notifications` | Idempotent in-app notifications, result-delivery worker and final-result email |
| `cache` | Redis wrapper (claim pointers, search results) |
| `health` | Liveness and readiness probes |

### Startup and shutdown (`core/lifespan.py`)

On startup the app:

1. Connects to Redis and creates a shared `httpx.AsyncClient`.
2. Loads the LaBSE, NER and NLI models (if `ML_LOAD_MODELS_ON_STARTUP`) and the multimodal model (if `MULTIMODAL_LOAD_ON_STARTUP`). A model that fails to load is logged and leaves its feature unavailable; it does not stop the API.
3. Makes sure the MinIO bucket exists.
4. Starts three background tasks in the API process:
   - the **verification job worker** (if `JOBS_ENABLED`);
   - the **result-delivery worker** (every 15 s);
   - the **escalation worker** (every 60 s).

On shutdown, the workers stop first, then the HTTP client, Redis and the database engine.

CORS allows `CORS_ORIGINS` without credentials. Clients send `Authorization: Bearer <token>` rather than cookies.

## Verification pipeline

[`pipeline/factory.py`](app/features/verification/pipeline/factory.py) builds one stage list that is used for Text & source claims (`POST /verify`, `/verify/async`) and photo cards. The two differ only in the normaliser: a photo card is always `HEADLINE_ONLY`, with no body.

| Stage | Critical | Summary | If it fails |
| --- | :-: | --- | --- |
| S01 Normaliser | yes | Bangla normalisation, source mode, claim scope (`HEADLINE_ONLY` / `HEADLINE_WITH_BODY`), identity hash | Submission fails |
| S02 Reuse lookup | | Redis pointer, then a database lookup for a reusable result | Full pipeline runs |
| S03 Query generator | | Search queries (see below) | Source check incomplete |
| S04 Source search | | Google News and the outlet's internal search. Records each provider call's outcome | Source check incomplete, never not-found |
| S05 Evidence retrieval | | Fetch with `httpx`. Falls back to Playwright for JS-only shells or bot walls. Blocks off-domain redirects. A walled host is skipped for 10 min | Source check incomplete |
| S06 Article extractor | | Title/body/date via JSON-LD, OpenGraph, per-outlet selectors, trafilatura, readability, BeautifulSoup. `dateModified` and crawl dates are never used | Source check incomplete |
| S07 Evidence ranker | | Score = 0.55 × LaBSE similarity + 0.25 × keyword overlap + 0.20 × domain match. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` breaks near-ties (> 3 candidates). Keeps up to `ML_MAX_RANKED_ARTICLES` | No ranked article |
| S08 Source correspondence | yes | `CONFIRMED` / `NOT_FOUND` / `INCOMPLETE`, plus the selected article | Submission fails |
| S09 Headline Alteration | | Claim headline vs. the selected **title** only | No verdict (`MODEL_UNAVAILABLE`) |
| S10 Body similarity | | TF-IDF cosine, Jaccard, normalised Levenshtein, LaBSE cosine (only when a body was sent) | Scores unavailable (never 0) |
| S11 Date verification | | Claimed day vs. `datePublished` day in Asia/Dhaka, only when the source is confirmed | No date status |
| S12 Result assembly | yes | Pipeline version, scope, correspondence strength, stage errors, plain-language reasoning | Submission fails |
| S13 Persistence | yes | Saves the result, articles and queries. Sends to expert review, writes the Redis pointer, notifies the submitter (once) | Submission fails |

If a non-critical stage fails, the run continues and the affected finding reports an explicit unavailable or incomplete state. Each stage's duration is stored in `verification_results.analysis_details.timings`.

**Source modes** ([`source_policy.py`](app/features/verification/source_policy.py)).

- **`CLAIMED_SOURCE` mode.** The outlet resolves through a URL or domain, a static alias, or a registry alias, and is active. Search is limited to that outlet.
  - S03 builds up to 6 `site:<domain>` queries: the full headline, all YAKE keywords (up to 8), the first 3 keywords, the first 4 keywords, and dated versions of the headline and all-keyword queries when a date is given.
  - The outlet's internal search runs too, when it has an `internal_search_url`. In the seed data these are Bangladesh Pratidin, Ittefaq and Prothom Alo.
- **`VERIFIED_SOURCES` mode.** Used when the outlet is missing, unrecognised or inactive.
  - Up to `SEARCH_FALLBACK_MAX_QUERIES` (default 3) phrasings: headline, all keywords, first 4 keywords.
  - Each phrasing runs once per group of `SEARCH_FALLBACK_DOMAIN_GROUP_SIZE` (default 5) verified domains, as a `site:a OR site:b …` Google News query. Internal search is not used.
  - The claim's identity includes a fingerprint of the active registry, so editing the registry starts a fresh verification context.
  - `SEARCH_VERIFIED_SOURCE_FALLBACK_ENABLED=false` turns this mode off.

**Source correspondence (S08).** S08 compares the claim headline with each ranked candidate's title, and any kicker line printed above it. It uses LaBSE similarity together with how many of the claim's keywords appear in the title and in the related passages (thresholds `THRESHOLD_CORR_*`).

- **`NOT_FOUND`** requires an *adequate* search: at least `THRESHOLD_SEARCH_MIN_SUCCESSFUL_CALLS` completed provider calls, and at least `THRESHOLD_SEARCH_MIN_SUCCESS_RATIO` of the attempted calls completed.
- **`INCOMPLETE`** is used otherwise. It is also used when the matching search result could not be fetched.

**Headline Alteration (S09)** ([`analysis/headline_comparison.py`](app/features/verification/analysis/headline_comparison.py)).

1. **Exact match** gives `MATCHED`. Normalisation is limited to NFC, removing zero-width characters, collapsing whitespace, and dropping one trailing `।.!?`.
2. **Otherwise two checks always run:**
   - *Deterministic material-difference rules* ([`material_differences.py`](app/features/verification/analysis/material_differences.py)): numbers, dates, negation, modality, scope, subject–object roles, attribution, denial, and named entities (NER).
   - *Semantic assessment*: NLI in both directions (title ⇒ headline decides) plus LaBSE cosine.
3. **Verdict:**
   - A material difference or established divergence gives `ALTERED`.
   - The same words in the same order, or established equivalence, gives `MATCHED`.
   - Otherwise there is no verdict, and `headline_check_status` is `MODEL_UNAVAILABLE` or `UNDETERMINED`.

The source body is never read here. For display, a `MATCHED` verdict is split into `EXACT_MATCHED` and `MEANING_PRESERVED`.

**Body similarity (S10)** ([`analysis/body_similarity.py`](app/features/verification/analysis/body_similarity.py)). These are four independent measurements, never a verdict.

- Levenshtein compares at most the first 20,000 characters.
- LaBSE compares sentence chunks of up to 450 characters.
- Each metric records whether it was available and why.

**Identity and reuse.**

- `hashing.compute_claim_hash` hashes headline, source key, claim scope, body, date and `VERIFICATION_PIPELINE_VERSION` (currently `v4.0-headline-title-body-scores`).
- **When a result is reusable** ([`reuse.py`](app/features/verification/reuse.py)): it still exists, comes from the current pipeline version, is an original computation (not a copy), and has no incomplete finding. Age does not matter.
- **What reuse does:** the result is copied onto the requester's own submission. Expert outcome is read live from the original.
- **Redis pointer lifetime:** 24 h, or 1 h for a `NOT_FOUND` result. After it expires, the database lookup still finds the result.

## Photo cards

`POST /photocard/verify/async` stores the image in MinIO (under `photocard/`) and creates the `PHOTO_CARD` submission, its extraction record and its job in one transaction. It then returns 202. If storage is down, it returns 503 and nothing is accepted. The job then runs these steps ([`claim_extraction.py`](app/features/photocard/claim_extraction.py)):

1. **Gemini extraction.** Gemini receives the original image and the catalogue of active verified sources with their aliases, and returns structured JSON. The outlet field must be one of those IDs or "not identified".
2. **Retries and key rotation.** Up to `GEMINI_ATTEMPTS_PER_BATCH × GEMINI_BATCHES` requests are made (default 3 × 3), with `GEMINI_BATCH_PAUSE_SECONDS` (10 s) between failed batches.
   - Retried: timeouts, network errors, 429, 5xx and malformed responses.
   - Not retried: 400/401/403/404.
   - On a 429, the next key from `GEMINI_API_KEY`, `GEMINI_API_KEY1`, `GEMINI_API_KEY2`, … is used.
3. **Outcome:**
   - No Gemini request succeeded: `API_FAILED`.
   - No usable headline (8+ characters including a letter): `INVALID_CONTENT`.
   - Otherwise the headline, the outlet (if active; else verified-sources mode) and the printed date (if parseable) become the claim. The claim goes through the pipeline as `HEADLINE_ONLY`.

Every attempt is stored in `photocard_extractions` and summarised on the result page.

## Text & image (multimodal)

`POST /multimodal/predict/async` validates the input (body ≥ 10 characters; JPEG/PNG/GIF/WebP up to 10 MB). It stores the image under `multimodal/` in MinIO and queues a job. The job then:

1. Compares BanglaBERT `[CLS]` and EfficientNet-B4 embeddings of the new item with the most recent `MULTIMODAL_DEDUP_CANDIDATE_LIMIT` predictions. All three thresholds must pass to count as a duplicate: combined ≥ 0.90, text ≥ 0.92, image ≥ 0.85.
2. Reuses the earlier prediction for a duplicate. Otherwise it runs `MultiFusionFake`: concatenated 768-d + 1792-d features → LayerNorm → MLP → `FAKE` / `NON_FAKE` with two confidence scores.

`MULTIMODAL_MAX_SEQ_LENGTH` (128) and `MULTIMODAL_IMG_SIZE` (380) must match training. The training notebook is [`MultiBanFake_BanglaBERT_EfficientNetB4.ipynb`](../MultiBanFake_BanglaBERT_EfficientNetB4.ipynb). Inference runs in a thread pool (`MULTIMODAL_INFERENCE_THREAD_WORKERS`).

## Background workers

**Verification job worker** ([`jobs.py`](app/features/verification/jobs.py)):

- Each job row is written in the same transaction as its submission.
- Workers claim jobs with `FOR UPDATE SKIP LOCKED`, so several workers or processes never take the same job.
- A running job sends a heartbeat every 30 s. A job with no heartbeat for `JOBS_STALE_AFTER_SECONDS` is reclaimed.
- There are two lanes: photo cards (`JOBS_PHOTOCARD_MAX_CONCURRENT`) and everything else (`JOBS_MAX_CONCURRENT`).
- Re-runs are idempotent: a submission already in expert review is left unchanged, and notifications are written once.

**Result-delivery worker** ([`notifications/delivery.py`](app/features/notifications/delivery.py)):

- Every 15 s it compares saved results with `result_deliveries`.
- It writes the submitter's in-app notifications (preliminary and final).
- It sends final-verdict email when SMTP is configured, with retry and backoff (at-least-once).

**Escalation worker** ([`expert_review/escalation.py`](app/features/expert_review/escalation.py)):

- Every 60 s it re-evaluates open claims against the voting limits.
- It escalates claims that have run out of time or votes, and notifies every active admin.

## Expert review engine

Implemented in [`expert_review/service.py`](app/features/expert_review/service.py).

**Votes**

- A vote contains a required overall verdict (`REAL` / `FAKE` / `MISLEADING` / `ALTERED`) and a justification of 50–5,000 characters.
- Source/content/date assessments are optional. Content and date apply only when the source is marked `CONFIRMED`.
- An expert can edit their vote while the claim is in `EXPERT_REVIEW`.

**Finalisation**

- Only the weighted overall tally counts, and only expert votes are added.
- A claim is finalised when all of these hold:
  - leader ≥ `verified_threshold`;
  - votes ≥ `min_expert_votes`;
  - leader − runner-up ≥ `lead_margin`;
  - the leader is unique.

**Vote weight**

- A vote counts 1.0 until the expert has `activation_threshold_votes` votes on finalised claims.
- After that, the weight comes from the active `credibility_weight_tiers` row that covers the expert's accuracy. Accuracy is the share of their overall votes that matched the final verdict.
- The weight is stored on the vote row, so later tier changes never alter past votes.

**Escalation**

- Escalation is triggered by `max_review_votes` or `max_review_hours`, whichever comes first. A NULL value means no limit.
- Experts cannot open or vote on an escalated claim (403).
- An admin's overall vote on an escalated claim becomes the final decision. On every other claim, admin votes are refused (403).

`voting_config` is a single-row table, edited by admins. Its defaults are M = 3, N = 10, T = 5.0 and margin = 1.0, with no limits. The default tiers, seeded by migration, are Novice 0–40% → 0.5, Competent 40–70% → 1.0, Expert 70–90% → 1.5 and Master 90–100% → 2.0.

## Authentication

- **Tokens.** HS256 JWTs. Access tokens last 15 min (`AUTH_ACCESS_TOKEN_TTL_SECONDS`).
- **Refresh.** Refresh tokens last 365 days and are rotated on every refresh. A token that was just rotated stays valid for 120 s, so a lost response does not log the user out. Logout revokes the token immediately.
- **Storage.** Refresh tokens and reset codes are stored only as SHA-256 hashes. Passwords use bcrypt (cost 12) and need 8+ characters, a digit and an uppercase letter.
- **Password reset.** A 6-digit code, valid for 10 minutes, is emailed to the user. If `EMAIL_SMTP_HOST` is empty, the code is logged instead.
- **Roles.** `user`, `expert`, `admin`. Registration always creates `user`. Admins create experts. The migration `seed_admin_user_001` creates `admin@gmail.com`.
- **Who can see a submission.** Pending and failed submissions are visible only to their owner, experts and admins (`submissions/access.py`). Completed ones are public by ID.

## Data model

| Table | Contents |
| --- | --- |
| `users`, `refresh_tokens`, `password_reset_tokens` | Accounts and credentials |
| `submissions` | Every claim: type, owner, headline/body/claimed outlet/date, status, processing phase, failure reason, content hash, reuse link |
| `verification_jobs` | Durable queue: status, attempts, heartbeat (`locked_at`), timestamps |
| `verification_results` | Automated result: source/content/date status, headline check status, correspondence measurements, `analysis_details` JSON (scope, findings, body scores, timings), expert-final fields |
| `retrieved_articles`, `source_evidence_queries` | Evidence articles (selected one first) and the queries that found them |
| `photocard_extractions` | Image key, Gemini attempts, extracted fields, extraction status |
| `multimodal_analysis` | Prediction, confidences, embeddings, image key, duplicate link |
| `verified_sources` | Outlet registry: canonical domain, names, aliases, selectors, internal search URL, URL patterns, active flag |
| `expert_profiles`, `expert_reviews` | Reviewer stats and individual votes (weight and tier at the time of the vote) |
| `credibility_weight_tiers`, `voting_config` | Admin-defined voting rules |
| `notifications`, `result_deliveries` | In-app notifications and the delivery/email ledger |

Migrations are in `app/db/migrations/versions/`. `alembic.ini` gets its database URL from the settings. To create a new migration:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
```

Back up an existing database before `alembic upgrade head`. Some migrations reset operational data; for example, `c7e2a9d4f1b3` deletes all submissions and the data that depends on them.

## Configuration

All settings are in [`app/core/config.py`](app/core/config.py) and read from the environment or `.env`. Each group uses a prefix. The template is [`.env.example`](.env.example).

| Prefix / key | Main settings (default) |
| --- | --- |
| general | `ENVIRONMENT` (development), `LOG_LEVEL` (INFO), `LOG_FORMAT` (`json` or `console`), `CORS_ORIGINS` (`["*"]`) |
| `AUTH_` | `SECRET_KEY` (required, ≥ 32 chars), `ACCESS_TOKEN_TTL_SECONDS` (900), `REFRESH_TOKEN_TTL_SECONDS` (31,536,000), `REFRESH_ROTATION_GRACE_SECONDS` (120), `BCRYPT_ROUNDS` (12) |
| `DB_` | `HOST`, `PORT` (5432), `NAME` (bangla_fact_guard), `USER`, `PASSWORD`, `POOL_SIZE` (10), `MAX_OVERFLOW` (20), `POOL_TIMEOUT` (30), `ECHO_SQL` |
| `REDIS_` | `HOST`, `PORT` (6379), `DB`, `PASSWORD`, `TTL_CLAIM_RESULT` (86,400), `TTL_NOT_FOUND_RESULT` (3,600), `TTL_SEARCH_RESULT` (21,600) |
| `SEARCH_` | `TOP_K_CANDIDATES` (15), `MIN_BODY_LENGTH_CHARS` (100), `PYGOOGLENEWS_MAX_RESULTS` (10), `VERIFIED_SOURCE_FALLBACK_ENABLED` (true), `FALLBACK_DOMAIN_GROUP_SIZE` (5), `FALLBACK_MAX_QUERIES` (3) |
| `ML_` | `EMBEDDING_MODEL_NAME` (`sentence-transformers/LaBSE`), `NLI_MODEL_NAME` (`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`), `NER_MODEL_NAME` (`arafatfahim/BanglaTag`), `MAX_RANKED_ARTICLES` (5), `MIN_RANK_SCORE` (0.05), `LOAD_MODELS_ON_STARTUP` (true), batch size and thread workers |
| `THRESHOLD_` | Source correspondence: `CORR_HEADLINE_SIM_ALONE` (0.85), `CORR_HEADLINE_SIM_STRONG` (0.72), `CORR_HEADLINE_SIM_PLAUSIBLE` (0.55), `CORR_KEYWORD_TITLE_PLAUSIBLE` (0.50), `CORR_KEYWORD_PASSAGE_PLAUSIBLE` (0.60), `CORR_KEYWORD_ONLY_TITLE` (0.70). Search adequacy: `SEARCH_MIN_SUCCESSFUL_CALLS` (2), `SEARCH_MIN_SUCCESS_RATIO` (0.5) |
| `GEMINI_` | `API_KEY` plus `API_KEY1…n`, `MODEL_NAME` (`gemini-2.0-flash`), `TIMEOUT_SECONDS` (20), `ATTEMPTS_PER_BATCH` (3, max 3), `BATCHES` (3, max 3), `BATCH_PAUSE_SECONDS` (10), `RETRY_BASE_DELAY_SECONDS` (1) |
| `PHOTOCARD_` | `MAX_IMAGE_BYTES` (10 MB) |
| `MINIO_` | `ENDPOINT` (localhost:9000), `ACCESS_KEY`, `SECRET_KEY`, `BUCKET_NAME` (bangla-fact-guard), `SECURE`, `PRESIGNED_URL_EXPIRY_SECONDS` (3,600) |
| `MULTIMODAL_` | `MODEL_DIR`, `DEVICE` (cpu/cuda), `LOAD_ON_STARTUP` (true), `MODEL_VERSION`, `MAX_SEQ_LENGTH` (128), `IMG_SIZE` (380), `TEXT_SIM_THRESHOLD` (0.92), `IMAGE_SIM_THRESHOLD` (0.85), `COMBINED_SIM_THRESHOLD` (0.90), `DEDUP_CANDIDATE_LIMIT` (100), `INFERENCE_THREAD_WORKERS` (2) |
| `EMAIL_` | `SMTP_HOST` (empty = no sending), `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `USE_TLS`, `FROM_ADDRESS`, `FROM_NAME`, `WEBSITE_URL` (link base in emails), `OTP_LENGTH` (6), `OTP_TTL_MINUTES` (10) |
| `JOBS_` | `ENABLED` (true), `MAX_CONCURRENT` (2), `PHOTOCARD_MAX_CONCURRENT` (4), `POLL_INTERVAL_SECONDS` (5), `STALE_AFTER_SECONDS` (120), `HEARTBEAT_INTERVAL_SECONDS` (30) |

Keys in `.env` that `config.py` does not define are ignored.

## API routes

All routes are under `/api/v1`. "Optional auth" means a bearer token links the submission to the account, but the route also works anonymously.

| Method and path | Access | Purpose |
| --- | --- | --- |
| `GET /health`, `GET /health/ready` | public | Liveness; readiness (PostgreSQL + Redis) |
| `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` | public | Account and token pair |
| `POST /auth/password-reset/request`, `/auth/password-reset/confirm` | public | Emailed reset code |
| `GET /auth/me`, `POST /auth/change-password` | signed in | Profile, password |
| `POST /verify/async` | optional auth | Queue a Text & source claim (202, `cached: true` when reused) |
| `POST /verify` | optional auth | Synchronous verification |
| `GET /verify/{id}/status`, `GET /verify/{id}` | visibility rule | Status/phase; full result |
| `POST /photocard/verify/async` | optional auth | Queue a photo card (multipart `image`) |
| `GET /photocard/{id}` | visibility rule | Photo-card state, extraction and result |
| `POST /multimodal/predict/async` | optional auth | Queue Text & image (multipart `headline`, `body_text`, `image`) |
| `POST /multimodal/predict` | optional auth | Synchronous prediction |
| `GET /multimodal/by-submission/{id}`, `/multimodal/predict/{prediction_id}`, `/multimodal/predictions` | public | Prediction detail, list |
| `GET /submissions/{id}` | visibility rule | Type, status and phase, so the client knows which detail endpoint to call |
| `GET /submissions/{id}/voting-details` | public, after final decision | Reviewer votes and justifications |
| `GET /users/me/submissions`, `/users/me/submissions/stats`, `GET/PUT /users/me/profile` | signed in | Own history (`q`, `state`, `type`, paging), stats, profile |
| `GET /notifications`, `/notifications/count`; `POST /notifications/{id}/read`, `/notifications/read-all` | signed in | In-app notifications |
| `GET /sources`, `GET /sources/{id}` | public | Verified sources (`q`, `language`, paging; `include_inactive` for admin use) |
| `POST /sources`, `PUT /sources/{id}`, `DELETE /sources/{id}` | admin | Manage sources |
| `GET /dashboard/stats`, `/dashboard/top-sources`, `/dashboard/explorer` | public | Platform stats, most-claimed sources, Fact Explorer (keyword, verdict, type, date filters) |
| `GET /expert/queue`, `/expert/queue/{id}` | expert, admin | Review queue (`q`, paging; admin `state` = all, escalated or review) |
| `POST /expert/queue/{id}/vote` | expert, admin | Vote (admins: escalated claims only) |
| `PUT /expert/reviews/{id}` | expert | Edit own vote |
| `GET /expert/history`, `/expert/stats`, `/expert/credibility` | expert, admin | Own votes and performance |
| `POST/GET /admin/experts`, `GET/PUT /admin/experts/{id}`, `POST /admin/experts/{id}/reset-password`, `/deactivate`, `/activate` | admin | Expert accounts |
| `GET /admin/dashboard`, `/admin/stats` | admin | Admin home and platform stats |
| `GET/POST/PUT /admin/credibility-tiers`, `PUT/DELETE /admin/credibility-tiers/{id}` | admin | Credibility tiers (`PUT` without an ID replaces the whole set) |
| `GET/PUT /admin/voting-config` | admin | Voting thresholds and limits |

"Visibility rule": results that are still pending or have failed return 404 to anyone except their owner, experts and admins.

## Scripts (`scripts/`, run from `backend/`)

| Script | Purpose |
| --- | --- |
| `seed_verified_sources.py` | Creates or updates `verified_sources` from `SOURCE_REGISTRY` ([`pipeline/source_registry.py`](app/features/verification/pipeline/source_registry.py)). Safe to run again |
| `fix_source_configs.py` | One-off repair of outdated selectors, URL patterns and internal search URLs for several outlets (Prothom Alo is not touched) |
| `report_verification_timings.py --limit 10 [--output file.md]` | Read-only report of per-stage timings for recent results |
| `reset_operational_data.py --apply [--database NAME]` | Backs up, then clears operational data for the 2026-10-03 schema cleanup. Keeps sources, tiers and voting config. Stop the API first |

Scripts that print Bangla to a Windows console need `PYTHONIOENCODING=utf-8`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio pytest-cov aiosqlite   # or: pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q                # 560 tests, coverage report, fails below 70%
.\.venv\Scripts\python.exe -m pytest -q --no-cov       # faster
.\.venv\Scripts\python.exe -m pytest tests/unit/verification -q --no-cov
```

The suite has unit tests only. `tests/unit/` mirrors `app/` (`admin`, `auth`, `cache`, `core`, `dashboard`, `expert_review`, `multimodal`, `nlp`, `notifications`, `photocard`, `search`, `shared`, `sources`, `submissions`, `users`, `verification/{analysis,pipeline/stages}`). Every service-logic module has its own `test_<module>.py`.

- **Database:** the `session` / `db` / `file_db` fixtures in `tests/unit/conftest.py` give an in-memory SQLite database with all tables. Builders are in `tests/helpers/db.py`.
- **External systems** are deterministic fakes in `tests/helpers/`:
  - `pipeline.py`: ML models, search and the source repository;
  - `gemini.py`: Gemini;
  - `playwright.py`: Playwright;
  - `multimodal.py`: a tiny model loader.

  So no network, GPU or model weights are needed.
- **Safety:** `tests/conftest.py` blanks the SMTP and Gemini settings from `.env`, so a test can never send email or use API quota.
- **Pinned hashes:** `tests/unit/shared/test_hashing.py` and `tests/unit/photocard/test_photocard_verification_stages.py` pin stored claim hashes. A refactor must not change them.

Linting and type-checking settings (`ruff`, `mypy`) are in `pyproject.toml`. Install them with `pip install -e ".[dev]"`.

## Troubleshooting

- **The NER check shows as unusable:** use a NER-trained checkpoint (`ML_NER_MODEL_NAME=arafatfahim/BanglaTag`, a fine-tuned BanglaBERT). The base `csebuetnlp/banglabert` has no NER head. The service checks entity labels at load time and maps institution and political-organisation labels to ORG.
- **LaBSE load fails or crashes on Windows:** increase the page file, set `OMP_NUM_THREADS=1`, or set `ML_LOAD_MODELS_ON_STARTUP=false`.
- **Source check incomplete for some outlets:** they may be behind Cloudflare. Install Chromium for Playwright, keep live test runs small and spaced out, and remember that a walled host is skipped for 10 minutes.
- **Another backend instance on the same database:** set `EMAIL_SMTP_HOST=` for that instance. Otherwise its delivery worker may also email submitters.
- **Standalone scripts that use the ORM:** `import app.shared.models_registry` first, so every model is registered.
