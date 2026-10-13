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
os.environ.update({k: "" for k in dotenv_values(".env") if k.upper().startswith("GEMINI_API_KEY")})


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"
