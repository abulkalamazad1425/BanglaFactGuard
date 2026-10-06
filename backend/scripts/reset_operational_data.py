"""Explicit, backed-up maintenance reset for the 2026-10-03 schema cleanup.

Stop all API/worker processes first. Run from backend with --apply. A database
override allows rehearsal on a restored copy. No source/weight/config seeding.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PROTECTED = ("verified_sources", "credibility_weight_tiers", "voting_config")
CLEAR = (
    "expert_reviews", "verification_results", "retrieved_articles",
    "source_evidence_queries", "photocard_extractions", "multimodal_analysis",
    "verification_jobs", "notifications", "submissions", "expert_profiles",
    "refresh_tokens", "password_reset_tokens",
)
LEGACY = (
    "user_feedback", "audit_log", "verification_logs", "verified_claims",
    "credibility_scores", "multimodal_predictions", "search_queries",
    "retrieved_articles_v2", "verification_results_v2", "expert_reviews_v2",
)
BEFORE_REVISION = "d1a7c3e5f9b2"
AFTER_REVISION = "a6d9e2f4b8c0"


def snapshot(connection, table):
    quote = connection.dialect.identifier_preparer.quote
    return {
        "rows": connection.execute(text(
            f"SELECT row_to_json(t) FROM {quote(table)} t ORDER BY id"
        )).scalars().all(),
        "columns": [list(r) for r in connection.execute(text(
            "SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, "
            "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
            "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
            "WHERE a.attrelid=to_regclass(:table) AND a.attnum>0 AND NOT a.attisdropped "
            "ORDER BY a.attnum"
        ), {"table": table})],
        "constraints": [list(r) for r in connection.execute(text(
            "SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid=to_regclass(:table) ORDER BY conname"
        ), {"table": table})],
        "indexes": [list(r) for r in connection.execute(text(
            "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' "
            "AND tablename=:table ORDER BY indexname"
        ), {"table": table})],
    }


def backup(url, destination):
    dump = shutil.which("pg_dump")
    restore = shutil.which("pg_restore")
    if not dump or not restore:
        raise RuntimeError("pg_dump and pg_restore are required before any changes")
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    result = subprocess.run([
        dump, "-h", url.host or "localhost", "-p", str(url.port or 5432),
        "-U", url.username, "-d", url.database, "-Fc", "-f", str(destination),
    ], env=env, capture_output=True)
    if result.returncode:
        raise RuntimeError("Backup failed; no reset was attempted")
    result = subprocess.run([restore, "--list", str(destination)], capture_output=True)
    if result.returncode:
        raise RuntimeError("Backup archive validation failed; no reset was attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.add_argument("--database", help="Optional isolated rehearsal database")
    args = parser.parse_args()
    url = make_url(get_settings().db.sync_url)
    if args.database:
        url = url.set(database=args.database)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = Path(__file__).resolve().parents[2] / "tmp" / f"cleanup-{stamp}"
    out.mkdir(parents=True)
    backup(url, out / "before.dump")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != BEFORE_REVISION:
            raise RuntimeError(f"Expected {BEFORE_REVISION}, found {revision}; refusing reset")
        tables = connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )).scalars().all()
        expected = set(CLEAR) | set(PROTECTED) | set(LEGACY) | {
            "users", "user_profiles", "alembic_version",
        }
        if set(tables) != expected:
            raise RuntimeError("Unexpected schema; inspect before resetting: " + str(set(tables) ^ expected))
        quote = connection.dialect.identifier_preparer.quote
        connection.exec_driver_sql(
            "LOCK TABLE " + ", ".join(quote(t) for t in tables) + " IN ACCESS EXCLUSIVE MODE"
        )
        protected = {t: snapshot(connection, t) for t in PROTECTED}
        admins = connection.execute(text(
            "SELECT row_to_json(u) FROM users u WHERE role='admin' ORDER BY id"
        )).scalars().all()
        if not admins:
            raise RuntimeError("No admin account exists; refusing to remove users")
        (out / "protected-before.json").write_text(
            json.dumps(protected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        migration_path = Path(__file__).resolve().parents[1] / (
            "app/db/migrations/versions/20261003_1200_a6d9e2f4b8c0_retire_legacy_schema.py"
        )
        spec = importlib.util.spec_from_file_location("cleanup_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        for table in CLEAR:
            connection.exec_driver_sql(f"DELETE FROM {quote(table)}")
        connection.execute(text("DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users WHERE role <> 'admin')"))
        connection.execute(text("DELETE FROM users WHERE role <> 'admin'"))
        connection.execute(text("UPDATE users SET total_submissions=0 WHERE role='admin'"))
        connection.execute(text("UPDATE user_profiles SET verification_count=0"))
        connection.execute(text("UPDATE alembic_version SET version_num=:revision"), {"revision": AFTER_REVISION})
        for table in PROTECTED:
            if snapshot(connection, table) != protected[table]:
                raise RuntimeError(f"Protected table changed: {table}; rolling back")
        retained = connection.execute(text("SELECT row_to_json(u) FROM users u ORDER BY id")).scalars().all()
        expected_admins = [dict(a, total_submissions=0) for a in admins]
        if retained != expected_admins:
            raise RuntimeError("Admin identity/settings mismatch; rolling back")
        counts = {t: connection.execute(text(f"SELECT count(*) FROM {quote(t)}")).scalar_one() for t in CLEAR}
        if any(counts.values()):
            raise RuntimeError("Operational records remain; rolling back")
    with engine.connect() as connection:
        for table in PROTECTED:
            if snapshot(connection, table) != protected[table]:
                raise RuntimeError(f"Post-commit verification failed for {table}")
    report = {
        "database": url.database, "revision": AFTER_REVISION,
        "protected_tables_unchanged": list(PROTECTED),
        "retained_admins": len(admins), "empty_tables": counts,
        "backup": str(out / "before.dump"),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
