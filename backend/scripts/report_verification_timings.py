"""Read-only timing report. Run from backend: python scripts/report_verification_timings.py.

No claims are rerun and no user text or account data is included.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.engine import get_engine


async def report(limit: int) -> str:
    engine = get_engine()
    engine.echo = False
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = (await connection.execute(text("""
                SELECT s.id, s.submission_type, s.created_at, r.pipeline_version,
                       r.avg_verification_time_ms, r.analysis_details,
                       j.attempts,
                       extract(epoch FROM (j.finished_at-j.created_at)) AS job_seconds
                FROM submissions s
                JOIN verification_results r ON r.submission_id=s.id
                LEFT JOIN verification_jobs j ON j.submission_id=s.id
                ORDER BY s.created_at DESC LIMIT :limit
            """), {"limit": limit})).mappings().all()
    finally:
        await engine.dispose()

    lines = ["# Recent source/text and photo-card verification timings", "",
             "Read-only snapshot. Historical stage durations cannot be reconstructed when not recorded.",
             "Job elapsed includes queue/retry time. Pipeline time excludes photo preprocessing and final commit.",
             "A missing stage was skipped or not recorded; it is not a measured zero.", "",
             "| Submission | Created (Asia/Dhaka) | Type | Version | Pipeline s | Job s | Attempts | Stage timings |",
             "|---|---|---|---|---:|---:|---:|---|"]
    samples: dict[str, list[float]] = {}
    details: list[str] = []
    for row in rows:
        timings = (row["analysis_details"] or {}).get("timings")
        total = row["avg_verification_time_ms"]
        total_s = f"{total / 1000:.3f}" if total is not None else "unavailable"
        job = f"{row['job_seconds']:.3f}" if row["job_seconds"] is not None else "unavailable"
        created = row["created_at"].astimezone(ZoneInfo("Asia/Dhaka"))
        lines.append(f"| {str(row['id'])[:8]} | {created} | {row['submission_type']} | "
                     f"{row['pipeline_version']} | {total_s} | {job} | {row['attempts']} | "
                     f"{'recorded' if timings else 'not recorded'} |")
        if not timings:
            continue
        details += ["", f"Execution {str(row['id'])[:8]} (cache hit: {timings.get('cache_hit', False)}):", ""]
        for group in ("preprocessing_ms", "stage_ms"):
            for stage, ms in timings.get(group, {}).items():
                details.append(f"- {stage}: {ms / 1000:.3f} s")
                samples.setdefault(stage, []).append(ms / 1000)
        details.append("")
    lines += details
    if samples:
        lines += ["", "## Measured stage summary", "",
                  "| Stage | Measured executions | Median s | Maximum s |",
                  "|---|---:|---:|---:|"]
        for stage, values in samples.items():
            lines.append(f"| {stage} | {len(values)} | {statistics.median(values):.3f} | {max(values):.3f} |")
    else:
        lines += ["", "No per-stage measurements exist for these historical executions.",
                  "New completed executions record all executed stages, including S13, in analysis_details.timings."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    output = asyncio.run(report(args.limit))
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Saved timing report: {args.output}")
    else:
        print(output)
