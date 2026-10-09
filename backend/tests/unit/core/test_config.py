"""Settings rules that protect behaviour: the Gemini request budget, key
rotation order, and `.env.example` staying in sync with the settings."""

import re
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings

from app.core.config import AppSettings, GeminiSettings, _numbered_gemini_keys

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
SECRETS = {"AUTH_SECRET_KEY", "GEMINI_API_KEY", "EMAIL_SMTP_PASSWORD"}


def test_gemini_budget_is_capped_at_nine_requests():
    assert GeminiSettings().max_requests == 9 and GeminiSettings().batch_pause_seconds == 10.0
    for field in ("attempts_per_batch", "batches"):
        with pytest.raises(ValueError):
            GeminiSettings(**{field: 4})


def test_gemini_keys_rotate_main_then_numbered_in_order_without_blanks_or_duplicates(monkeypatch):
    for name in ("GEMINI_API_KEY1", "GEMINI_API_KEY2", "GEMINI_API_KEY10"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY10", "ten")
    monkeypatch.setenv("GEMINI_API_KEY2", "two")
    monkeypatch.setenv("GEMINI_API_KEY1", "one")
    keys = GeminiSettings(api_key="main", api_keys=_numbered_gemini_keys()).all_api_keys
    assert keys[:2] == ["main", "one"] and keys.index("two") < keys.index("ten")
    assert GeminiSettings(api_key="x", api_keys=["x", " ", "y", "your-gemini-api-key-here"]).all_api_keys == ["x", "y"]
    assert not GeminiSettings(api_key="", api_keys=[]).is_configured


def test_log_level_is_validated():
    assert AppSettings(log_level="debug").log_level == "DEBUG"
    with pytest.raises(ValueError):
        AppSettings(log_level="LOUD")


def test_env_example_names_only_real_settings_once_and_leaves_secrets_blank():
    known: set[str] = set()
    for field_name, field in AppSettings.model_fields.items():
        sub = field.annotation
        if isinstance(sub, type) and issubclass(sub, BaseSettings):
            prefix = sub.model_config.get("env_prefix", "")
            known |= {f"{prefix}{n}".upper() for n in sub.model_fields}
        else:
            known.add(field_name.upper())
    entries = [
        (m.group(1), m.group(2).strip())
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip()))
    ]
    names = [name for name, _ in entries]
    assert set(names) <= known, sorted(set(names) - known)
    assert len(names) == len(set(names))
    assert all(value == "" for name, value in entries if name in SECRETS)
