"""Unit-test environment.

Settings are fixed before the app is imported, so the developer's `.env`
(real SMTP credentials, Gemini keys, database) is never used by a test.
Postgres-only column types are rendered as JSON on SQLite, which the
database-backed unit tests use (see tests/helpers/db.py).
"""

from __future__ import annotations

import os

from dotenv import dotenv_values
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

os.environ.update(
    ENVIRONMENT="development",
    DB_NAME="test",
    AUTH_SECRET_KEY="test-only-jwt-signing-key-not-a-secret-0123456789",
    EMAIL_SMTP_HOST="",
    GEMINI_API_KEY="",
    ML_LOAD_MODELS_ON_STARTUP="false",
    MULTIMODAL_LOAD_ON_STARTUP="false",
)
# Blank values win over `.env` (load_dotenv never overrides) and are ignored
# by the numbered Gemini key reader.
os.environ.update({k: "" for k in dotenv_values(".env") if k.upper().startswith("GEMINI_API_KEY")})


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover - trivial shim
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):  # pragma: no cover - trivial shim
    return "JSON"
