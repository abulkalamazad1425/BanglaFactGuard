# BanglaFactGuard

BanglaFactGuard is a Bangla news-claim verification system with three applications: an **Angular website**, a **FastAPI backend**, and a **Chrome browser extension**. Users can check a claim against its stated news source, verify a photocard's extracted headline, or request a preliminary text-and-image prediction. Automated findings and expert-finalized verdicts are presented separately.

The website and extension use English interface text while accepting Bangla claims.

## Applications and technology

| Application | Location | Technology | Purpose |
| --- | --- | --- | --- |
| Website | `frontend/` | Angular 19, TypeScript, SCSS, Angular Material/CDK | Claim submission, detailed evidence, Fact Explorer, account history, expert review and administration |
| API and verification | `backend/` | Python, FastAPI, SQLAlchemy, Alembic | Authentication, verification, model inference, durable jobs and result persistence |
| Chrome extension | `extension/` | Preact, Vite, Chrome Manifest V3 | Submit from the current page, capture selected areas, track results and show notifications |
| Database | External service | PostgreSQL | Users, submissions, analyses, evidence, review records and job queue |
| Cache | Docker/local service | Redis | Cached search, extraction and verification data |
| Image storage | Docker/local service | MinIO | Uploaded images and temporary signed image URLs |

## Verification methods

| Method | Submission type | Inputs | Automated output |
| --- | --- | --- | --- |
| Text & source | `SOURCE_BASED` | Headline, claimed source; optional body and claimed publication date | Separate source, content and date findings with supporting evidence |
| Photo card | `PHOTO_CARD` | Image, claimed source; optional claimed publication date | OCR/extracted headline verified against the supplied source |
| Text & image | `MULTIMODAL` | Headline, body text and image | Preliminary `FAKE` / `NON_FAKE` prediction |

### Source-based and photocard verification

The shared verification pipeline normalizes the claim, resolves its source, checks cached results, searches for source articles, extracts and ranks evidence, and compares the claim with the retrieved report. Content comparison uses local embedding, NLI and NER services plus deterministic checks for material changes. A text submission with a body checks both the headline and body statements; a photocard checks its extracted headline only.

Photocard headline extraction uses OCR, optionally Gemini, and a deterministic fallback. Gemini is used for headline extraction, not for the local content-comparison decision. Model names and thresholds are configurable; see [backend configuration](backend/.env.example) and [content-comparison design](docs/photocard-content-comparison.md).

Result dimensions are independent:

- **Source:** `CONFIRMED`, `NOT_FOUND` or `INCOMPLETE`.
- **Content:** `MATCHED`, `ALTERED` or `INCOMPLETE` when source evidence is available.
- **Date:** `MATCHED`, `MISMATCHED` or `INCOMPLETE` when applicable.

A missing source is not automatically a fake verdict. An incomplete search is not a confident negative. A date mismatch does not make matching content false. Automated confidence measurements are not the probability that a claim is true.

**Photocard date policy:** dates read from the image may remain archival backend metadata, but are not displayed as an extracted-date field in the website or extension. They are not compared with other dates and do not generate date warnings. This also suppresses older saved extraction warnings. The user-supplied publication date can still be checked against the source article's publication date.

### Multimodal analysis

The multimodal model combines **BanglaBERT** text features and **EfficientNet-B4** image features. The body is the model's text input; the headline is retained for display. Text, image and combined embedding similarity are used for duplicate detection.

`FAKE` and `NON_FAKE` are preliminary model predictions. They are distinct from the expert-finalized overall verdict: `FAKE`, `REAL`, `MISLEADING` or `ALTERED`.

## Users and permissions

| User | Website | Extension |
| --- | --- | --- |
| Anonymous | Submit claims and access available results without login | Submit, track local guest activity and receive result notifications |
| Registered user | Account-linked submissions, history, notifications and profile settings | Sign in, submit and view this account's extension activity |
| Expert | Review assigned/available claims, vote and inspect review history/statistics | Submit and track claims; link to the website's expert workspace |
| Admin | Manage experts, sources, credibility settings and administrative review | Submit and track claims; link to admin workspace; edit connection settings |

The extension's **API base URL, Website URL and Save connection** controls are admin-only. The background worker also checks authorization and revalidates the admin role with the current backend before changing connection settings. ON/OFF and notification preferences remain available to all users.

Website and extension login sessions are separate. Anonymous extension history belongs to that Chrome installation and does not automatically become account-owned after login. Expert review and administrative work take place on the website.

## Background processing and results

Text, photocard and asynchronous multimodal submissions can return an acknowledgement with a submission ID while processing continues on the backend. Durable jobs are stored in PostgreSQL's `verification_jobs` table and drained by an in-process worker. Accepted jobs survive application restarts; abandoned jobs are reclaimed after their heartbeat becomes stale. An application process with the worker enabled must be running to execute jobs.

Typical lifecycle:

```text
PENDING -> PROCESSING -> EXPERT_REVIEW -> FINALIZED
                |              |
              FAILED        ESCALATED
                         (admin resolution)
```

An automated result can be ready while expert review is still pending. Source-based and photocard checks may take around 1.5–2 minutes, but completion time depends on retrieval, OCR, models and server load.

All three methods use the website detail route `/verify/{submission_id}`. The page resolves the submission type before fetching its report.

## Chrome extension features

- Side panel beside the current webpage, with Verify, Activity and Account views.
- Independent headline/body entry through typing, copy/paste, selected-text buttons or right-click actions; imported text can replace or append to a field.
- Image upload or a user-selected screenshot rectangle, followed by preview, further crop, reset and remove.
- Local text/image drafts, account-separated activity, brief result cards and links to detailed website reports.
- Background polling, preliminary/final/failure notifications and an unread toolbar badge.
- ON/OFF switch: pauses new extension activity and notifications while accepted server jobs continue; turning ON resumes tracking.

The screenshot API captures the visible viewport internally, then the extension immediately crops it locally. Only the selected area is saved/uploaded; the full scrolling page is not captured. Click the pinned toolbar icon on the intended website before selecting text or capturing, especially after changing sites. Chrome-internal pages and other restricted surfaces require paste/upload instead.

Pending results are normally checked about every 30 seconds; expert-finalization follow-up is slower. Browser closure, sleep, disabled extensions or OS notification settings can delay or suppress desktop alerts. Activity and the unread badge provide a fallback. See the [extension guide](extension/README.md) for complete behavior and limitations.

## Repository structure

```text
BanglaFactGuard/
|-- backend/
|   |-- app/
|   |   |-- api/                 # API routing and middleware
|   |   |-- core/                # Configuration and application lifecycle
|   |   |-- db/migrations/       # Alembic migrations
|   |   |-- features/            # Auth, submissions, verification, photocard,
|   |   |                        # multimodal, expert review, admin and more
|   |   `-- shared/              # Shared models, dependencies and utilities
|   |-- scripts/                 # Source seeding and maintenance utilities
|   |-- tests/                   # Unit and integration tests
|   |-- .env.example
|   |-- docker-compose.yml       # Redis and MinIO (not PostgreSQL)
|   |-- requirements.txt
|   `-- run.py
|-- frontend/
|   |-- src/app/                 # Angular features, services, routes and layouts
|   |-- src/environments/        # Development/production API configuration
|   |-- src/styles.scss          # Shared green/light visual theme
|   `-- package.json
|-- extension/
|   |-- src/                     # Preact panel, worker, capture and local storage
|   |-- public/manifest.json
|   |-- tests/
|   |-- dist/                    # Generated unpacked Chrome build
|   |-- IMPLEMENTATION_PLAN.md
|   |-- TESTING.md
|   `-- README.md
|-- docs/
`-- README.md
```

The root-level `index.html` and `multimodal.html` are older standalone clients. The current website is the Angular application in `frontend/`; do not use a static Python HTTP server to run it.

## Local setup

### Prerequisites

- Python 3.11 or newer, with compatible PyTorch/model dependencies.
- Node.js 22 and npm for the website and extension.
- PostgreSQL with a database and credentials configured for this project.
- Docker Compose for the included Redis and MinIO services, or equivalent local services.
- Desktop Chrome 120 or newer for the extension.
- Bangla OCR support and trained multimodal weights for the corresponding verification methods.

Commands below use PowerShell. Run each application's commands from its own directory, in separate terminals. On Linux/macOS, use the virtual environment's `bin/python` in place of `.venv\Scripts\python.exe`.

### 1. Backend environment and dependencies

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install "python-jose[cryptography]" bcrypt email-validator
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

The additional install supplies authentication/validation dependencies imported by the current backend but not listed in `requirements.txt`. Configure `.env` with your own values; keep an existing working environment rather than replacing it.

| Configuration | Purpose |
| --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL connection |
| `REDIS_HOST`, `REDIS_PORT` | Redis connection |
| `MINIO_*` | Image storage endpoint, credentials and bucket |
| `AUTH_SECRET_KEY` | JWT signing key; separate from the general `SECRET_KEY` setting |
| `ML_*` | Local embedding, NLI, NER models and device |
| `OCR_*` | OCR engine configuration, including `OCR_TESSERACT_CMD` where needed |
| `GEMINI_API_KEY`, `GEMINI_MODEL_NAME` | Optional Gemini headline extraction |
| `MULTIMODAL_MODEL_DIR`, `MULTIMODAL_DEVICE`, `MULTIMODAL_LOAD_ON_STARTUP` | Trained text/image model loading |
| `JOBS_ENABLED`, `JOBS_*` | Background worker and recovery settings |
| `EMAIL_*` | Password-reset email delivery |

Use your own secrets and service credentials rather than treating example values as deployment configuration. The current settings definitions are in [config.py](backend/app/core/config.py).

### 2. Services, database and sources

Create the PostgreSQL database matching `DB_NAME` using your PostgreSQL tools. The included Compose file starts **Redis and MinIO only**:

```powershell
# From backend/
docker compose up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/seed_verified_sources.py
```

The source-seeding script creates or updates the registered publisher configurations used by source-based verification. Migrations include an initial admin seed; use an appropriately configured admin account for administration. Public registration creates a regular user account.

For photocard OCR, install Tesseract with Bengali language data and configure its executable path when needed, or use the configured EasyOCR option. Initial model/OCR use may download weights.

Set `MULTIMODAL_MODEL_DIR` to a directory containing:

```text
img_backbone.pt
text_backbone.pt
classifier.pt
tokenizer/
```

These trained artifacts must be provided separately. `MULTIMODAL_LOAD_ON_STARTUP=false` skips multimodal model loading for development, but Text & image prediction then remains unavailable.

Start the API:

```powershell
# From backend/
.\.venv\Scripts\python.exe run.py
```

### 3. Angular website

In a new terminal, from the repository root:

```powershell
cd frontend
npm ci
npm start
```

Open [the website](http://localhost:4200). Development API configuration lives in `frontend/src/environments/environment.ts` and defaults to `http://localhost:8000/api/v1`.

### 4. Chrome extension

In another terminal, from the repository root:

```powershell
cd extension
npm ci
npm run build
```

Then:

1. Enter `chrome://extensions` in Chrome's address bar.
2. Enable **Developer mode** and click **Load unpacked**.
3. Select **`extension/dist`**, not the source directory.
4. Pin **BanglaFactGuard — Quick Verify**.
5. Open a news/Facebook webpage and click the pinned toolbar icon.
6. Choose a verification mode and submit as a guest or sign in.

The API must be running for submission and result checks. The website need not be open, but its server must be available for detailed report links. Rebuild and click **Reload** on the Chrome extensions page after changing extension code.

Only an admin can change connection URLs through the extension UI. For an initial deployment where the default local API is unavailable, configure `extension/src/shared.js` and the API host permission in `extension/public/manifest.json` before building.

### Local addresses

| Service | Address |
| --- | --- |
| Website | [localhost:4200](http://localhost:4200) |
| Backend API base | `http://localhost:8000/api/v1` |
| API documentation | [localhost:8000/docs](http://localhost:8000/docs) |
| MinIO API | `http://localhost:9000` |
| MinIO console | [localhost:9001](http://localhost:9001) |
| PostgreSQL / Redis | Configured locally; default ports 5432 / 6379 |

## Main API routes

All routes below are relative to `/api/v1`. Consult the running API documentation for schemas and access requirements.

| Operation | Route |
| --- | --- |
| Account registration/login | `POST /auth/register`, `POST /auth/login` |
| Session/profile | `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Registered publishers | `GET /sources` |
| Queue a text claim | `POST /verify/async` |
| Text status/result | `GET /verify/{id}/status`, `GET /verify/{id}` |
| Queue a photocard | `POST /photocard/verify/async` |
| Photocard status/result | `GET /photocard/{id}` |
| Queue multimodal analysis | `POST /multimodal/predict/async` |
| Submission type/status lookup | `GET /submissions/{id}` |
| Multimodal result | `GET /multimodal/by-submission/{id}` |
| Account notifications | `GET /notifications` |

Synchronous verification endpoints also remain available. The extension uses asynchronous submission to avoid waiting for inference/search in its panel.

## Builds and tests

### Website

```powershell
cd frontend
npm run build
npm test
```

The production build is generated under `frontend/dist/bangla-fact-guard/` (browser assets in its `browser/` directory). Its API base is `/api/v1`: configure the hosting server to proxy that path to FastAPI and support Angular route fallback. Karma tests require a compatible Chrome installation.

### Extension

```powershell
cd extension
npm test
npm run build
# Rebuild when source files change:
npm run dev
```

Automated extension tests cover result mapping, forms, account isolation, page-access handling, notifications and admin-only connection changes using simulated browser APIs. They do not replace installed-Chrome screenshot or OS-notification checks. See [extension testing notes](extension/TESTING.md).

### Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio pytest-cov aiosqlite
.\.venv\Scripts\python.exe -m pytest
```

The suite includes deterministic model/service fakes and database tests. Dependency and database requirements vary by test; the default pytest configuration includes coverage reporting and a coverage threshold. For focused extension-related checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_multimodal_background.py tests/unit/test_photocard_background.py tests/unit/test_photocard_extraction_failure.py -q --no-cov
```

## Troubleshooting

- **Unknown claimed source:** seed/configure the registered publisher list and use the publisher named in the claim, not necessarily the website displaying it.
- **Claims remain queued:** keep `JOBS_ENABLED=true`, the backend running, and the database/model/storage dependencies available.
- **Multimodal unavailable:** check trained weights, tokenizer, model startup logs and MinIO.
- **Photocard extraction fails:** check OCR installation/Bengali language data and image readability. Failed extraction is not a fake-news verdict.
- **Facebook capture access error:** activate the Facebook tab and click the pinned extension toolbar icon before selecting an area. A side-panel button alone does not grant access to a new site.
- **No desktop notification:** check extension ON state, its notification preference, Chrome/OS permissions and Activity. Browser sleep/closure can delay delivery.
- **Connection settings missing:** the extension intentionally exposes them only to admins.
- **Submission acknowledgement lost:** check Activity or account history before retrying. Existing APIs do not provide a universal cross-request idempotency key.

## Further documentation

- [Extension setup and usage](extension/README.md)
- [Extension implementation plan](extension/IMPLEMENTATION_PLAN.md)
- [Extension verification notes and manual checks](extension/TESTING.md)
- [Current statement-by-statement content comparison](docs/photocard-content-comparison.md)
- [AI engineering design](docs/06-ai-engineering-design.md)
- [Database cleanup notes](docs/database-cleanup-2026-10-03.md)

Design documents can describe earlier iterations; the current implementation and API schemas determine runtime behavior.
