# BanglaFactGuard — Backend

FastAPI service for BanglaFactGuard: authentication, source-based / photo-card /
multimodal verification, durable background jobs, expert review and
notifications. Full project documentation, configuration tables and the
verification design are in the [repository README](../README.md) and
[`docs/`](../docs/) (start with
[`backend-codebase-guide.md`](../docs/backend-codebase-guide.md)).

## Quick start (PowerShell, from `backend/`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"     # or: -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium   # browser fallback for protected pages
if (!(Test-Path .env)) { Copy-Item .env.example .env }      # then fill in your own values
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe run.py
```

`AUTH_SECRET_KEY` (at least 32 characters) is required; the app refuses to
start without it. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

The multimodal model weights (`img_backbone.pt`, `text_backbone.pt`,
`classifier.pt`, `tokenizer/`) are not distributed with the code; point
`MULTIMODAL_MODEL_DIR` at them, or set `MULTIMODAL_LOAD_ON_STARTUP=false`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov
```

`tests/unit/test_identity_hash_golden.py` and
`tests/unit/test_api_response_snapshots.py` pin persisted hashes and API
responses; a refactor must not change them.
