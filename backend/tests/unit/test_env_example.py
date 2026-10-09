"""`.env.example` must only name settings that exist, and never carry a value
for a secret."""

import re
from pathlib import Path

from pydantic_settings import BaseSettings

from app.core.config import AppSettings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
SECRETS = {"AUTH_SECRET_KEY", "GEMINI_API_KEY", "EMAIL_SMTP_PASSWORD"}


def _known_env_names() -> set[str]:
    names: set[str] = set()
    for field_name, field in AppSettings.model_fields.items():
        sub = field.annotation
        if isinstance(sub, type) and issubclass(sub, BaseSettings):
            prefix = sub.model_config.get("env_prefix", "")
            names |= {f"{prefix}{n}".upper() for n in sub.model_fields}
        else:
            names.add(field_name.upper())
    return names


def _entries() -> dict[str, str]:
    out = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def test_every_example_variable_maps_to_a_setting():
    unknown = set(_entries()) - _known_env_names()
    assert not unknown, f"not read by any setting: {sorted(unknown)}"


def test_example_has_no_duplicate_keys():
    keys = [
        m.group(1)
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^([A-Z0-9_]+)=", line.strip()))
    ]
    assert len(keys) == len(set(keys))


def test_secrets_are_blank_in_example():
    entries = _entries()
    assert all(entries.get(k, "") == "" for k in SECRETS)
