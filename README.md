# BanglaFactGuard

BanglaFactGuard checks Bangla news claims. It has three parts: an **Angular website**, a **FastAPI backend**, and a **Chrome extension**. A user can check a typed claim against news sources, check a photo card (a headline image shared on social media), or get a preliminary prediction for a news story with an image. The automated system only produces preliminary findings. The final verdict on every claim (**Fake, Real, Misleading or Altered**) comes from a weighted vote by human experts. An administrator decides the claim if the experts cannot agree.

The website and extension interfaces are in English. Claims are in Bangla.

| Part | Folder | Technology | What it does |
| --- | --- | --- | --- |
| Website | [`frontend/`](frontend/README.md) | Angular 19, TypeScript, SCSS, Angular Material/CDK | Claim submission, result reports, Fact Explorer, account history, notifications, expert review and administration |
| API and verification | [`backend/`](backend/README.md) | Python 3.11+, FastAPI, SQLAlchemy 2 (async), Alembic, PyTorch, sentence-transformers, Playwright | Authentication, the verification pipeline, model inference, durable background jobs, expert voting, notifications and email |
| Chrome extension | [`extension/`](extension/README.md) | Preact, Vite, Chrome Manifest V3 side panel | Submit from the page you are reading, select text, capture a screen area, and track results with desktop notifications |
| Database | external | PostgreSQL | Users, submissions, results, evidence, expert reviews, notifications and the job queue |
| Cache | Docker (`backend/docker-compose.yml`) | Redis 7 | Pointers to reusable results and cached search results |
| Image storage | Docker (`backend/docker-compose.yml`) | MinIO | Uploaded photo cards and Text & image pictures, served through temporary signed URLs |

## Verification methods

| Method (UI name) | Submission type | Input | Automated output |
| --- | --- | --- | --- |
| **Text & source** | `SOURCE_BASED` | Headline (required). Claimed outlet, article body and claimed publication date are optional | Source finding, Headline Alteration verdict and date finding. If a body was given, four body similarity scores |
| **Photo card** | `PHOTO_CARD` | Image only (JPEG/PNG/WebP/GIF, max 10 MB) | Gemini reads the headline, outlet and printed date from the card. The headline then goes through the same checks as Text & source |
| **Text & image** | `MULTIMODAL` | Article body (≥ 10 characters) and an image (required). Headline optional | Preliminary **Likely Fake / Likely Real** prediction from a BanglaBERT + EfficientNet-B4 model |

All three methods share one detail page on the website: `/verify/{submission_id}`.

### Claimed source or verified sources

A Text & source claim or photo card is checked in one of two modes. The rule is the same everywhere ([`source_policy.py`](backend/app/features/verification/source_policy.py)):

- **Claimed source**: the claim names an outlet that resolves to a known, active outlet. Search and article fetching are limited to that outlet's registered domains.
- **Verified sources**: no outlet was given, the outlet is not recognised, or it is a deactivated verified source. Instead, the claim is searched across all **active verified sources** using Google News only, with domains grouped into `site:a OR site:b …` queries. An unknown outlet is never treated as a verified publisher. If the registry is empty, the search returns *incomplete* rather than an unrestricted web search.

Set `SEARCH_VERIFIED_SOURCE_FALLBACK_ENABLED=false` to turn off verified-sources mode. Claims without a usable outlet are then rejected (`404 source_not_found` for text, and a failed submission for photo cards).

The source seeding script registers ten Bangla outlets as verified sources: Prothom Alo, Bangladesh Pratidin, The Daily Star Bangla, Jugantor, Ittefaq, Kaler Kantho, Samakal, Manab Zamin, Daily Inqilab and Naya Diganta. Admins can add, edit or deactivate sources on the website.

### How a text or photo-card claim is checked

Both methods run the same 13-stage pipeline ([`pipeline/factory.py`](backend/app/features/verification/pipeline/factory.py)):

| Stage | What it does |
| --- | --- |
| S01 Normaliser | Normalises the Bangla text, decides the source mode and computes the claim's identity hash |
| S02 Reuse lookup | Reuses an earlier identical, complete result: Redis pointer first, then the database |
| S03 Query generator | Claimed-source mode: up to 6 `site:`-restricted queries (full headline, all keywords, first 3 and first 4 keywords, plus dated versions when a date is given). Verified-sources mode: up to 3 phrasings |
| S04 Source search | Google News (`pygooglenews`) and, if configured, the outlet's own site search. Off-source results are discarded. Records each provider call's outcome so a failed search is never reported as an empty one |
| S05 Evidence retrieval | Fetches candidate pages with `httpx`. Falls back to headless Chromium (Playwright) for JavaScript-rendered or bot-protected pages. Rejects redirects that leave the outlet's domains |
| S06 Article extractor | Title, body and publication date from JSON-LD, OpenGraph, per-outlet selectors, trafilatura, readability or BeautifulSoup |
| S07 Evidence ranker | Ranks articles by LaBSE similarity, keyword overlap and domain match. A multilingual cross-encoder only breaks near-ties |
| S08 Source correspondence | Decides **Source**: did the outlet publish *this* report? Selects the source article |
| S09 Headline Alteration | Compares the claim headline with the selected article's **title only** |
| S10 Body similarity | Computes four body similarity scores, only when a body was submitted |
| S11 Date verification | Compares the claimed date with the article's `datePublished` (calendar day, Asia/Dhaka) |
| S12 Result assembly | Builds one explainable result. Never produces an overall Fake/Real verdict |
| S13 Persistence | Saves the result and evidence, sends the claim to expert review, writes the Redis pointer and notifies the submitter |

Only local models are used for these decisions: LaBSE embeddings, a multilingual NLI model (mDeBERTa-v3 XNLI) and a BanglaBERT-based NER model. Gemini is used only to read photo cards.

### Automated findings

Each finding is reported on its own and never combined into a verdict:

| Finding | Stored values | Shown as |
| --- | --- | --- |
| **Source**: relevant article from the claimed source (or from the verified sources) | `CONFIRMED`, `NOT_FOUND`, `INCOMPLETE` | Found / Not found in claimed source (or *in verified sources*) / Check incomplete |
| **Headline Alteration**: claim headline vs. the source title | `MATCHED`, `ALTERED`, or no verdict | Exact Matched / Meaning Preserved / Altered. With no verdict, a reason: `SOURCE_NOT_FOUND`, `SOURCE_CHECK_INCOMPLETE`, `SOURCE_TITLE_MISSING`, `MODEL_UNAVAILABLE` or `UNDETERMINED` |
| **Body similarity**: claim body vs. source body | TF-IDF cosine, Jaccard, normalised Levenshtein, LaBSE cosine (0–1 each) | Raw scores only. A missing score is shown as unavailable, never as 0 |
| **Date**: claimed date vs. the article's publication date | `MATCHED`, `MISMATCHED`, `INCOMPLETE` | Matched / Mismatched / Could not be determined |

**How the headline is compared.** An exact match (after Unicode NFC, removing zero-width characters, collapsing whitespace and dropping one trailing `।.!?`) is *Exact Matched*. Otherwise two checks always run:

- Deterministic rules look for a material difference: numbers, dates, negation, modality, scope, subject–object reversal, attribution, denial, or named entities.
- An NLI check in both directions, plus LaBSE cosine similarity, looks for evidence that the meaning is the same or different.

Any material difference or clear semantic divergence gives *Altered*. *Meaning Preserved* requires positive evidence of the same meaning. "No conflict found" alone is never enough to match.

**What the findings do not mean:**

- A source that was not found does not make a claim fake.
- An incomplete search is not a confident negative.
- A date mismatch does not make a matching headline false.
- Similarity scores are not probabilities that a claim is true.

The website's [FAQ](frontend/src/app/features/faq/faq.html) (`/faq`) explains these results to users.

### Photo cards

The user uploads only the image. Gemini (default `gemini-2.0-flash`) receives the original image and the list of active verified sources with their aliases. It must:

- transcribe the headline exactly as printed;
- pick the outlet only if its name, logo or alias is visible on the card;
- transcribe the printed date, never infer one.

These values become the claim's headline, claimed outlet and claimed date. Gemini makes at most 9 requests per card (3 batches of 3, with a 10 s pause between batches). Several API keys (`GEMINI_API_KEY`, `GEMINI_API_KEY1`, `GEMINI_API_KEY2`, …) are rotated when one hits its rate limit. There is no OCR fallback.

- **All Gemini requests fail:** the submission fails with a "temporarily unavailable" message and no verification runs.
- **No readable headline:** the submission fails with an explanation.
- **Headline readable, but the outlet is missing, unrecognised or inactive:** the card is checked in verified-sources mode, and any outlet text on the card is kept for reference.

### Text & image (multimodal)

The model ([training notebook](MultiBanFake_BanglaBERT_EfficientNetB4.ipynb), trained on the MultiBanFake dataset) combines:

- the BanglaBERT `[CLS]` features of the article body (768-d);
- EfficientNet-B4 image features (1792-d).

A fused classifier head outputs `FAKE` / `NON_FAKE`, shown as *Likely Fake* / *Likely Real*. The headline is stored for display only. Before inference, the text, image and combined embeddings are compared with recent predictions. A near-duplicate reuses the earlier prediction (thresholds `MULTIMODAL_*_SIM_THRESHOLD`).

### Reusing earlier results

A claim's identity is a hash of its normalised headline, body, source (or the verified-sources registry fingerprint), date, claim scope and pipeline version. If an identical claim already has a complete result from the current pipeline version, that result is **copied** onto the new submission. Expert review state is not copied. It is read live from the original, so finalising the original updates every copy.

Results are reused regardless of age. A result with an incomplete check is never reused. If the same user resubmits an identical Text & source claim, they get their existing submission back.

## Expert review and final verdicts

Every automated result goes to the expert queue, for all three methods.

- **Voting.** Experts cast an **overall verdict**: `REAL`, `FAKE`, `MISLEADING` or `ALTERED`, with a written justification of at least 50 characters. For Text & source and Photo card claims, they can also record their own Source, Headline and Date assessments. These are for reference only and do not affect the outcome. Experts can edit their vote while the claim is still in review.
- **Weighted consensus.** Only the overall vote decides the claim. It is finalised when all of these hold:
  - the leading verdict's weighted score is at least **T**;
  - at least **M** experts have voted;
  - the leader is ahead of the runner-up by at least the **lead margin**;
  - the leader is unique (a tie never finalises).

  Defaults: M = 3, T = 5.0, margin = 1.0. Admins set these values on the website (stored in the `voting_config` table).
- **Credibility.** A vote has weight 1.0 until the expert has **N** votes on finalised claims (default N = 10). After that, the weight comes from the admin-defined credibility tiers, based on how often the expert's vote matched the final verdict. Default tiers: Novice 0.5, Competent 1.0, Expert 1.5, Master 2.0.
- **Escalation.** An admin can set a vote cap (`max_review_votes`) and a time limit (`max_review_hours`). An undecided claim goes to the admin as soon as either is exceeded. A background sweep checks the time limit every 60 s. On an escalated claim, the admin's overall vote becomes the final decision. On every other claim, admins can only view.
- **Transparency.** Once a claim is finalised, anyone (including signed-out visitors) can see each reviewer's vote and justification on the result page. An admin's decision is marked as such.

## Users and permissions

| User | Website | Extension |
| --- | --- | --- |
| Anonymous | Submit claims and open results by link | Submit, track this browser's guest activity and receive notifications |
| Registered user | Account-linked submissions, *My Submissions* with search and filters, in-app notifications, profile and password settings | Sign in, submit and track this account's extension activity |
| Expert | Expert queue, review page, vote history, reviewer performance in settings | Same as a registered user |
| Admin | Admin dashboard (escalated claims, slow reviews, recent decisions and activity), expert accounts, verified sources, credibility tiers and voting settings, and the admin review queue | Same as a registered user, plus the API/website **Connection settings** |

Registration always creates a regular `user`. Expert accounts are created by an admin. The first migrations seed one admin account (`admin@gmail.com`). Change its password after setup.

Website and extension sign-ins are separate. Results that are still pending or have failed are visible only to their owner and staff. Completed results are public by link and appear in the Fact Explorer. Anonymous submissions can be reached by anyone with their unguessable ID.

## Background processing and lifecycle

Submissions are accepted at once (HTTP 202 with a submission ID) and processed in the background:

- Each accepted submission writes a row in the `verification_jobs` table in the same transaction, so an accepted job cannot be lost.
- An in-process worker claims jobs with `FOR UPDATE SKIP LOCKED` and sends heartbeats. A running job whose heartbeat is older than `JOBS_STALE_AFTER_SECONDS` (default 120 s) is reclaimed, so jobs survive restarts.
- Photo cards run in their own lane (`JOBS_PHOTOCARD_MAX_CONCURRENT`, default 4). This way, Gemini retries never block text or Text & image jobs (`JOBS_MAX_CONCURRENT`, default 2).

The worker only runs while the API process is running with `JOBS_ENABLED=true`.

```text
PENDING -> PROCESSING -> EXPERT_REVIEW -> FINALIZED
               |               |
             FAILED        ESCALATED -> FINALIZED (admin decision)
```

While a submission is `PROCESSING`, a finer phase is shown: `QUEUED`, `EXTRACTING` (photo cards), `VERIFYING`, `DONE` or `FAILED`.

The automated result is ready once the submission reaches `EXPERT_REVIEW`. A Text & source or Photo card check usually takes one to two minutes. The time depends on outlet search, page fetching, Gemini and server load.

## Notifications and email

Notifications go only to the person who submitted the claim. There is no public feed.

- **Signed-in submitters** get an in-app notification when the preliminary result is ready and another when the expert verdict is final. The final verdict is also emailed to the account address.
- **Result-delivery worker.** It checks saved results every 15 s. Email is retried with backoff. If SMTP is not configured (`EMAIL_SMTP_HOST` empty), emails stay queued and password-reset codes are written to the log instead.
- **Delivery guarantee.** Email delivery is at-least-once: a crash at the wrong moment can send a duplicate.
- **Extension.** It tracks its own user's submissions. It shows a desktop notification and an unread badge for the preliminary result, the final verdict, and failures.

## Repository structure

```text
BanglaFactGuard/
|-- backend/                      FastAPI service (see backend/README.md)
|   |-- app/
|   |   |-- api/                  v1 router, middleware, exception handlers
|   |   |-- core/                 settings, constants, lifespan (models, workers), logging
|   |   |-- db/                   async engine and Alembic migrations
|   |   |-- features/             auth, users, submissions, verification (pipeline + analysis),
|   |   |                         photocard, multimodal (+ model files), expert_review, admin,
|   |   |                         dashboard, notifications, sources, search, nlp, cache, health
|   |   `-- shared/               base model/repository, dependencies, email, labels, utils
|   |-- scripts/                  source seeding, source repair, timing report, data reset
|   |-- tests/                    unit tests (mirror of app/) and shared fakes
|   |-- .env.example  alembic.ini  docker-compose.yml  pyproject.toml  requirements.txt  run.py
|-- frontend/                     Angular website (see frontend/README.md)
|-- extension/                    Chrome extension (see extension/README.md)
|-- output/                       project deliverables: SRS, proposal, final report,
|                                 infographic and presentation
|-- MultiBanFake_BanglaBERT_EfficientNetB4.ipynb   multimodal model training notebook
`-- README.md
```

## Local setup

### Prerequisites

- Python 3.11 or newer (developed on 3.13).
- Node.js 22 and npm.
- PostgreSQL (developed on 17), with a database for the project.
- Docker Compose for Redis and MinIO (or your own local instances).
- Desktop Chrome 120 or newer for the extension.
- A Gemini API key for photo cards.
- The multimodal model weights for Text & image (see [step 3](#3-models)).
- Disk space and memory for the local models (LaBSE, mDeBERTa NLI, BanglaTag NER, and the cross-encoder). They download from Hugging Face on first start.

The commands below use PowerShell on Windows. On Linux/macOS, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`. Run each application in its own terminal.

### 1. Backend environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Fill in `.env` with your own values. `AUTH_SECRET_KEY` (at least 32 characters) is required, and the API will not start without it. Generate one:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Every setting is listed in [backend/README.md](backend/README.md#configuration) and defined in [config.py](backend/app/core/config.py).

### 2. Services, database and sources

Create the PostgreSQL database named in `DB_NAME` (default `bangla_fact_guard`). Then, from `backend/`:

```powershell
docker compose up -d                                        # Redis :6379 and MinIO :9000/:9001 (not PostgreSQL)
.\.venv\Scripts\python.exe -m alembic upgrade head          # schema, admin account, default credibility tiers
.\.venv\Scripts\python.exe scripts/seed_verified_sources.py # the ten verified Bangla outlets
```

### 3. Models

- **Local NLP models** (LaBSE, NLI, NER, cross-encoder) download automatically on first start. Set `ML_LOAD_MODELS_ON_STARTUP=false` to start without loading them. Verification will then report the affected checks as unavailable.
- **Multimodal model.** It needs a folder with `img_backbone.pt`, `text_backbone.pt`, `classifier.pt` and `tokenizer/`.
  - `classifier.pt`, `config.json` and `tokenizer/` are in [`backend/app/features/multimodal/multimodal_model/`](backend/app/features/multimodal/multimodal_model).
  - The two backbone files (about 70 MB and 440 MB) are not in git. Copy them there from the training output.
  - Then set `MULTIMODAL_MODEL_DIR=app/features/multimodal/multimodal_model`.
  - Set `MULTIMODAL_LOAD_ON_STARTUP=false` to start without it. Text & image is then unavailable.
- **Photo cards** need `GEMINI_API_KEY`.

### 4. Start the API

```powershell
# from backend/
.\.venv\Scripts\python.exe run.py     # uvicorn on 127.0.0.1:8000 with auto-reload
```

### 5. Website

```powershell
cd frontend
npm ci
npm start                              # http://localhost:4200, calls http://localhost:8000/api/v1
```

### 6. Chrome extension

```powershell
cd extension
npm ci
npm run build                          # creates extension/dist
```

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and select **`extension/dist`** (not the `extension` folder).
3. Pin **BanglaFactGuard — Browser Extension**, open a news page and click the toolbar icon. The side panel opens beside the page.

After changing extension code, run `npm run build` again and click **Reload** on `chrome://extensions`.

### Local addresses

| Service | Address |
| --- | --- |
| Website | <http://localhost:4200> |
| API base | `http://localhost:8000/api/v1` |
| API docs (Swagger / ReDoc) | <http://localhost:8000/docs>, <http://localhost:8000/redoc> |
| Health / readiness | `GET /api/v1/health`, `GET /api/v1/health/ready` (checks PostgreSQL and Redis) |
| MinIO API / console | `http://localhost:9000`, <http://localhost:9001> |
| PostgreSQL / Redis | `localhost:5432` / `localhost:6379` |

## API overview

All routes are under `/api/v1`. The complete list is in [backend/README.md](backend/README.md#api-routes), and request/response schemas are at `/docs`.

| Area | Main routes |
| --- | --- |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/password-reset/request`, `/auth/password-reset/confirm`, `/auth/change-password`; `GET /auth/me` |
| Text & source | `POST /verify/async` (queue), `GET /verify/{id}/status`, `GET /verify/{id}`; `POST /verify` (synchronous) |
| Photo card | `POST /photocard/verify/async` (multipart `image`), `GET /photocard/{id}` |
| Text & image | `POST /multimodal/predict/async` (multipart `headline`, `body_text`, `image`), `GET /multimodal/by-submission/{id}`; `POST /multimodal/predict` (synchronous) |
| Any submission | `GET /submissions/{id}` (type and status), `GET /submissions/{id}/voting-details` |
| Account | `GET /users/me/submissions`, `/users/me/submissions/stats`, `GET/PUT /users/me/profile`, `GET /notifications`, `/notifications/count` |
| Public | `GET /sources`, `/dashboard/stats`, `/dashboard/top-sources`, `/dashboard/explorer` |
| Expert | `GET /expert/queue`, `/expert/queue/{id}`, `POST /expert/queue/{id}/vote`, `PUT /expert/reviews/{id}`, `GET /expert/history`, `/expert/stats`, `/expert/credibility` |
| Admin | `/admin/experts…`, `/admin/dashboard`, `/admin/stats`, `/admin/credibility-tiers…`, `/admin/voting-config`; `POST/PUT/DELETE /sources…` |

## Tests and builds

| Part | Command (from the part's folder) | Notes |
| --- | --- | --- |
| Backend | `.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio pytest-cov aiosqlite` then `.\.venv\Scripts\python.exe -m pytest -q` | Unit tests only. 560 tests, about 90% coverage, 70% coverage required. Add `--no-cov` for a faster run. No network, GPU or model weights needed |
| Extension | `npm test` | 34 Node tests for the worker and shared logic, using simulated Chrome APIs |
| Website | `npm run build` | Production build into `frontend/dist/bangla-fact-guard/browser/`. The website has no unit test target |

For the production website, serve `frontend/dist/bangla-fact-guard/browser/` with fallback to `index.html` for Angular routes. Proxy `/api/v1` to FastAPI, because the production build calls the API at the relative path `/api/v1`.

## Troubleshooting

- **API exits at startup:** `AUTH_SECRET_KEY` is missing or shorter than 32 characters.
- **Claims stay queued:** keep `JOBS_ENABLED=true` and the API running. Interrupted jobs resume about 120 s after a restart.
- **`404 source_not_found` on a text claim:** verified-sources mode is turned off (`SEARCH_VERIFIED_SOURCE_FALLBACK_ENABLED=false`) and the outlet could not be resolved.
- **Source "Check incomplete":** the search or page fetch failed. Common causes:
  - Some outlets block automated traffic (Cloudflare). A blocked host is skipped for 10 minutes.
  - Avoid running many verifications against the same outlet in a short time.
- **Photo card failed:**
  - "Temporarily unavailable" means no Gemini request succeeded. Check `GEMINI_*`, your quota and the network.
  - "No valid headline" means the card could not be read.
  - The result page lists each failed attempt. A failed read is not a fake-news verdict.
- **Text & image unavailable:** check `MULTIMODAL_MODEL_DIR` (all four items must be present), the startup logs and MinIO.
- **LaBSE fails to load on Windows:** increase the page file, or set `ML_LOAD_MODELS_ON_STARTUP=false` for development. Setting `OMP_NUM_THREADS=1` can help with native crashes.
- **No final-result email:** set `EMAIL_SMTP_*` (a Gmail account needs an app password) and `EMAIL_WEBSITE_URL`. Never commit credentials.
- **Extension problems:** see [extension/README.md](extension/README.md#troubleshooting).

## Further documentation

- [Backend](backend/README.md): architecture, pipeline, configuration, data model, routes, scripts and tests
- [Website](frontend/README.md): pages, structure, configuration and build
- [Chrome extension](extension/README.md): installation, use, notifications, permissions and limits
- [`output/`](output/): SRS, proposal, final report, infographic and presentation
