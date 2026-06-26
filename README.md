# BanglaFactGuard — Multimodal Source-Based Fact Verification Engine

BanglaFactGuard is a production-grade, async pipeline designed to verify news claims in the Bangla language against declared publication sources, and to predict the authenticity of multimodal news content. 

It contains two primary verification systems:
1. **Source-Based Verification Pipeline (12-stage)**: Checks whether a claimed source actually published an article using Internal Site Searching against primary Bangla domains, a 6-tier fallback article extraction system (JSON-LD, Trafilatura, Readability, etc.), LaBSE semantic similarity, MMARCO Cross-Encoder re-ranker, and DeBERTa NLI textual entailment analysis.
2. **Multimodal Verification Pipeline**: A high-performance inference engine that classifies news as `FAKE` or `NON_FAKE` using a dual-encoder architecture (**BanglaBERT** for text and **EfficientNet-B4** for images). Features advanced 3-level similarity deduplication backed by PostgreSQL array operations and MinIO object storage.

---

## Project Structure

```text
BanglaFactGuard/
├── backend/
│   ├── app/
│   │   ├── main.py             # App Lifespan and Factory
│   │   ├── core/               # Configuration & Logging
│   │   ├── db/                 # Database Session & Migrations
│   │   ├── features/           # Package-by-Feature Modules
│   │   │   ├── multimodal/     # Multimodal Image + Text fake-news detection
│   │   │   ├── verification/   # Core 12-stage fact-check pipeline
│   │   │   ├── articles/       # Retrieved articles & models
│   │   │   ├── sources/        # Source registry CRUD
│   │   │   ├── nlp/            # ML models (LaBSE, DeBERTa, BanglaBERT)
│   │   │   ├── search/         # Web search clients
│   │   │   └── ...             # Users, Expert Review, Auth, etc.
│   │   └── shared/             # Cross-cutting concerns & base classes
│   ├── tests/                  # Pytest Unit & Integration Test Suite
│   ├── docker-compose.yml      # Infra containers (Redis & MinIO)
│   ├── requirements.txt        # Backend dependencies
│   └── .env.example            # Environment variables template
└── frontend/
    ├── index.html              # AngularJS Client App for Source Verification
    └── multimodal.html         # Client App for Multimodal Image Verification
```

---

## 🚀 Backend Setup & Execution

### 1. Prerequisites
- Python 3.11 or higher installed on your system.
- PostgreSQL database installed locally on port 5432.
- Docker installed (for running Redis and MinIO).

### 2. Install Dependencies
Change to the backend directory and install the required Python packages:
```bash
cd backend
python -m pip install -r requirements.txt
```

### 3. Setup Infrastructure (PostgreSQL, Redis, MinIO)
- **PostgreSQL**: Ensure it is listening on `localhost:5432`. Create a database named `bangla_fact_guard` (default user: `postgres`, password: `user`).
- **Redis & MinIO**: Start the caching and object storage services using Docker Compose:
  ```bash
  cd backend
  docker-compose up -d
  ```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and configure your settings:
```bash
copy .env.example .env
```
*Make sure to configure the `MULTIMODAL_MODEL_DIR` path in `.env` to point to the directory where your trained `img_backbone.pt`, `text_backbone.pt`, and `classifier.pt` files are located.*

### 5. Run Database Migrations
Initialize your database schema:
```bash
alembic upgrade head
```

### 6. Running the Backend Server
Start the backend server using `uvicorn` (or the custom `run.py` if available):
```bash
uvicorn app.main:app --reload
```
- The backend API will be available at: **`http://localhost:8000`**
- Interactive Swagger documentation will be available at: **`http://localhost:8000/docs`**

---

## 🧪 Running Tests

A comprehensive unit and integration test suite is located in the `tests/` directory. Machine learning models and external API clients are globally mocked using fixtures so that tests run instantly without requiring GPU/model weight downloads.

Run the tests using pytest:
```bash
python -m pytest
```

---

## 🎨 Frontend Setup & Execution

We provide two beautifully styled frontends using a modern glassmorphism design system to interact with the distinct verification pipelines.

### How to Run:
Ensure the backend FastAPI server is running on **`http://localhost:8000`**, then open either file directly in your browser or run a simple local server:
```bash
cd frontend
python -m http.server 3000
```

1. **Source-Based Verification Pipeline UI:** 
   Navigate to **`http://localhost:3000/index.html`**
   - Inputs: Headline, Source URL, Body, Date.
   - Outputs: Circular Confidence Meter, Execution Details, Manipulation Warnings, and Found Articles Evidence.

2. **Multimodal API Verification UI:** 
   Navigate to **`http://localhost:3000/multimodal.html`**
   - Inputs: Headline, Body Text, and Image Upload.
   - Outputs: `FAKE`/`NON_FAKE` predictions, confidence bars, and real-time similarity metrics indicating if the result was served from the backend's duplicate-detection cache.
