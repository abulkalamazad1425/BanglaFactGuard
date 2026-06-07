# BanglaFactGuard — Multimodal Source-Based Fact Verification Engine

BanglaFactGuard is a production-grade, async pipeline designed to verify news claims in the Bangla language against declared publication sources. It checks whether a claimed source actually published the article using a 12-stage verification pipeline combining neural search, NLP keyword and entity extraction, and DeBERTa NLI textual entailment analysis.

---

## Project Structure

```
BanglaFactGuard/
├── backend/
│   ├── app/                    # FastAPI Application Core
│   │   ├── main.py             # App Lifespan and Factory
│   │   ├── api/                # API Endpoints & Dependencies
│   │   ├── core/               # Configuration & Logging
│   │   ├── db/                 # Database Session & Migrations
│   │   ├── models/             # SQLAlchemy ORM Models
│   │   ├── repositories/       # DB CRUD Repositories
│   │   ├── schemas/            # Pydantic Schemas
│   │   ├── services/           # ML and Registry Services
│   │   ├── pipelines/          # 12-stage Verification Orchestration
│   │   └── utils/              # Text processing & sanitization utilities
│   ├── tests/                  # Pytest Unit & Integration Test Suite
│   │   ├── conftest.py         # Test fixtures and ML mocks
│   │   ├── unit/               # Normalization, query gen, classification tests
│   │   └── integration/        # End-to-end pipeline and endpoint tests
│   ├── pyproject.toml          # Project metadata and dependencies
│   ├── requirements.txt        # Backend dependencies
│   ├── .env.example            # Environment variables template
│   └── docker-compose.yml      # Containerized Postgres + Redis config
└── frontend/
    └── index.html              # Stunning AngularJS Client App with Glassmorphism
```

---

## 🚀 Backend Setup & Execution

### 1. Prerequisites
- Python 3.11 or higher installed on your system.
- Docker installed (optional, for Postgres/Redis).

### 2. Install Dependencies
Change to the backend directory and install the required Python packages:
```bash
cd backend
python -m pip install -r requirements.txt
```

### 3. Setup Databases (PostgreSQL & Redis)
You can run the required databases using Docker Compose:
```bash
docker-compose up -d
```
This launches:
- **PostgreSQL** on `localhost:5432` (user: `postgres`, password: `postgres`, DB: `bangla_fact_guard`)
- **Redis** on `localhost:6379` (no password)

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and configure your settings:
```bash
copy .env.example .env
```
Fill in the `SEARCH_BRAVE_API_KEY` in the `.env` file if you plan to use Brave Search. (If not configured, the pipeline will fallback to Google News RSS and DuckDuckGo scrapers).

### 5. Running the Backend Server
Start the Uvicorn ASGI server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
- The backend API will be available at: **`http://localhost:8000`**
- Interactive Swagger documentation will be available at: **`http://localhost:8000/docs`**

---

## 🧪 Running Tests

A comprehensive unit and integration test suite is located in the `tests/` directory. Machine learning models and external API clients are globally mocked using fixtures so that tests run instantly (~1 second) and require zero GPU/model weight downloads.

Run the tests using pytest:
```bash
python -m pytest
```

---

## 🎨 Frontend Setup & Execution

The frontend is a single-page application built with **AngularJS** and styled using **Vanilla CSS** with a stunning glassmorphism design system. It handles user inputs (headline, source, body, date) and sends asynchronous POST requests to the local backend verification engine.

### How to Run:
1. Ensure the backend FastAPI server is running on **`http://localhost:8000`**.
2. Run a simple HTTP server in the `frontend` directory:
   ```bash
   cd ../frontend
   python -m http.server 3000
   ```
3. Open your browser and navigate to: **`http://localhost:3000/index.html`** (or simply double-click the `frontend/index.html` file to open it directly in a browser).

### Features:
- **Interactive Verdict Badge:** Highlights verdict color-coded (Green for `TRUE`, Red for `FALSE`, Orange for `PARTIALLY_TRUE`, Gray for `NOT_FOUND`).
- **Circular Confidence Meter:** A dynamic, animated SVG progress ring displaying the pipeline's overall confidence.
- **Detailed Score Progression:** Shows exact similarity, entity matching, keyword overlap, and contradiction metrics.
- **Manipulation Warnings:** Alerts user if the headline was altered, numerals swapped, or body texts altered.
- **Evidence Card Deck:** Displays matching article headers, metadata, and matched snippets retrieved by neural search.
