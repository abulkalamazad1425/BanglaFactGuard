# Database cleanup — 3 October 2026

Migration: `d1a7c3e5f9b2` → `a6d9e2f4b8c0`.

The live application now uses `retrieved_articles`, `verification_results`, and
`expert_reviews` for submission-based data. Their former `_v2` names and the
obsolete claim-based tables have been retired. All Python references were
updated; historical migrations remain intact.

Removed tables: legacy `verified_claims`, `search_queries`, `credibility_scores`,
`multimodal_predictions`, the three old unsuffixed tables, `user_feedback`,
`verification_logs`, and `audit_log`. Feedback and audit-history endpoints/models
were removed. Pipeline stage diagnostics go to application logs.

`verification_jobs` remains the durable queue, including retries and restart
recovery. Operational records were cleared from submissions, results, evidence,
OCR, multimodal analyses, expert reviews/profiles, notifications, jobs, and tokens.
Only the existing admin account and its profile remain; activity counters are
zero. Existing account credentials/settings were preserved. Admin must sign in
again because refresh/reset tokens were cleared. Registration and future expert
creation remain available.

## Protected data

Before/after checks verified exact row, column, constraint, and index equality for
`verified_sources`, `credibility_weight_tiers`, and `voting_config`. The ten source
records, including IDs, timestamps, nullable fields and ordered selector/alias
arrays, are documented in `backend/app/features/verification/pipeline/source_registry.py`.
No source-seeding or configuration-fixing script was executed.

## Verification

- Successfully restored the pre-cleanup PostgreSQL backup into an isolated database
  and rehearsed the complete migration/reset there before touching the live database.
- Verified ORM table/column compatibility, source alias lookup, and result/job
  writes on PostgreSQL, rolling back the test writes.
- 57 focused end-to-end, photo-card job/recovery, expert-voting, and result-reuse
  tests passed after cleanup changes.
- Full unit suite: 303 passed, 11 failed. The unchanged baseline had 303 passed,
  10 failed and 1 setup error. The same tests were unsuccessful: five stale
  multimodal service mocks, one embedding test, one photo-card extraction test,
  three query-generation tests, and the SQLite source-resolution test. The last
  previously failed during legacy-index setup and now reaches its unsupported
  PostgreSQL JSONB alias query on SQLite. This cleanup does not claim a green
  full suite or change the pipeline to accommodate those unrelated failures.
- AST comparison verified text verification, photo-card, multimodal service, cache
  lookup and background worker logic remain identical after normalizing renamed
  class references. No scoring/classification, OCR or model-inference changes.
- Restarted the backend and durable worker. Readiness, admin statistics, credibility
  tiers, voting configuration, and sources endpoints returned HTTP 200. OpenAPI
  no longer exposes feedback or audit-history routes. Final inspection found 17
  application tables plus Alembic metadata, one admin, ten sources, four weight
  tiers, and no operational records. Protected-table equality was checked again
  after API calls. The isolated rehearsal database was removed after validation.

## Maintenance and recovery

`backend/scripts/reset_operational_data.py --apply` is an explicit one-time
maintenance tool, never a startup hook. It requires the old revision, backs up
first, checks the table allowlist, locks tables, and performs schema/data changes
in one transaction with protected-data/admin checks before committing. A different
revision is rejected to prevent accidental repeat resets. Stop API and worker
processes before use. `--database` supports rehearsal on an isolated restored copy.

The final live backup and machine-readable report are in the git-ignored directory
`tmp/cleanup-20261003T091311002754Z/`. An earlier backup, baseline comparison and
test logs are in `tmp/database-cleanup-20261003/`. Backups contain account data and
must remain local and outside version control. The final archive is `before.dump`.

This migration cannot reconstruct deleted records through downgrade. To recover,
stop the backend, restore the pre-cleanup archive into an empty database, restore
the matching previous application code, verify protected records, then switch the
application connection and restart. Do not restore over an active database.

Only the application's claim/search/article/embedding cache namespaces were cleared;
unrelated Redis keys and object-storage uploads were not deleted.
