"""Keyword-ranked application search (Fact Explorer): OR matching of unique
keywords, ranking by distinct keywords matched, phrase/headline tie-breaks,
escaping, and filtering/ranking before pagination with a matching count."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import ARRAY
from sqlalchemy.ext.compiler import compiles

from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.repository import SubmissionRepository
from app.shared.utils.keyword_search import escape_like, split_keywords
from tests.unit.db_helpers import add_completed_submission, make_session_factory


@compiles(ARRAY, "sqlite")
def array_sqlite(type_, compiler, **kw):
    return "JSON"


def test_split_keywords_is_unique_normalised_and_drops_stopwords():
    assert split_keywords("  ঢাকা   বাস দুর্ঘটনা ঢাকা ") == ["ঢাকা", "বাস", "দুর্ঘটনা"]
    assert split_keywords("The bus, and the CRASH!") == ["bus", "CRASH"]
    assert split_keywords("") == []
    assert escape_like("50%_a\\b") == "50\\%\\_a\\\\b"


@pytest.fixture
async def repo_with_rows():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
    session = factory()
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = {}
    # newest first by created_at, so ranking (not date) must decide the order
    for i, (key, headline, body) in enumerate([
        ("one", "ঢাকায় নতুন সেতু", None),
        ("two", "বাস দুর্ঘটনায় আহত ১০", "ঢাকা শহরে"),
        ("three_scattered", "দুর্ঘটনা: ঢাকা থেকে ছাড়া বাস উল্টে", None),
        ("three_phrase", "ঢাকা বাস দুর্ঘটনা নিয়ে তদন্ত", None),
        ("none", "নির্বাচন কমিশনের বৈঠক", None),
        ("pct", "দাম বেড়েছে 50% পর্যন্ত", None),
    ]):
        sub, _ = await add_completed_submission(session, headline=headline, body=body, submitter_id=None)
        sub.created_at = base + timedelta(hours=10 - i)
        rows[key] = sub
    await session.flush()
    yield SubmissionRepository(session), rows
    await session.close()
    await engine.dispose()


async def test_partial_matches_are_returned_and_ranked_by_distinct_keywords(repo_with_rows):
    repo, rows = repo_with_rows
    found, total = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা")
    ids = [r.id for r in found]
    assert total == 4 and rows["none"].id not in ids  # OR: any keyword matches
    # all three keywords first (exact phrase wins the tie), then two... then one
    assert ids[:2] == [rows["three_phrase"].id, rows["three_scattered"].id]
    assert ids[2] == rows["two"].id
    assert ids[3] == rows["one"].id


async def test_pagination_happens_after_ranking_and_count_is_stable(repo_with_rows):
    repo, rows = repo_with_rows
    page1, total1 = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা", limit=2, offset=0)
    page2, total2 = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা", limit=2, offset=2)
    assert total1 == total2 == 4
    assert [r.id for r in page1 + page2] == [
        rows["three_phrase"].id, rows["three_scattered"].id, rows["two"].id, rows["one"].id
    ]


async def test_like_wildcards_are_literal(repo_with_rows):
    repo, rows = repo_with_rows
    found, total = await repo.search(keyword="50%")
    assert total == 1 and found[0].id == rows["pct"].id
    _, total = await repo.search(keyword="%")
    assert total == 1


async def test_empty_query_keeps_existing_order(repo_with_rows):
    repo, rows = repo_with_rows
    found, total = await repo.search(keyword="   ")
    assert total == 6 and found[0].id == rows["one"].id  # newest first, unchanged
