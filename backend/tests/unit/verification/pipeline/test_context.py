from app.core.constants import ClaimScope, SourceStatus
from app.features.verification import source_policy
from app.features.verification.pipeline.context import build_context
from tests.helpers.pipeline import article


def test_scope_follows_the_body_and_an_explicit_headline_only_drops_it():
    with_body = build_context("শিরোনাম", "prothomalo.com", news_body="বডি টেক্সট")
    assert with_body.claim_scope == ClaimScope.HEADLINE_WITH_BODY and with_body.raw_news_body == "বডি টেক্সট"
    for kwargs in ({}, {"news_body": "   "}):
        ctx = build_context("শিরোনাম", "prothomalo.com", **kwargs)
        assert ctx.claim_scope == ClaimScope.HEADLINE_ONLY and ctx.raw_news_body is None
    # a photo card is headline-only even if a body is passed by mistake
    card = build_context("শিরোনাম", None, news_body="বডি", claim_scope=ClaimScope.HEADLINE_ONLY)
    assert card.raw_news_body is None and card.raw_claimed_source == ""


def test_retrieval_failure_means_every_fetch_or_every_extraction_failed():
    ctx = build_context("h", "s")
    assert not ctx.retrieval_failed
    ctx.fetch_attempted, ctx.fetch_errors = 3, 2
    assert not ctx.retrieval_failed
    ctx.fetch_errors = 3
    assert ctx.retrieval_failed
    ctx.fetch_errors, ctx.extraction_attempted, ctx.extraction_errors = 0, 2, 2
    assert ctx.retrieval_failed


def test_publisher_and_confirmation_depend_on_the_mode():
    ctx = build_context("h", "prothomalo.com")
    ctx.normalized_source = "prothomalo.com"
    assert ctx.publisher_for_url("https://other.com/a") == "prothomalo.com" and ctx.publisher_for_url(None) is None
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    ctx.verified_scope = source_policy.VerifiedScope([source_policy.VerifiedPublisher("jugantor.com", "যুগান্তর", ["jugantor.com"], {})])
    assert ctx.publisher_for_url("https://www.jugantor.com/a/1") == "jugantor.com"
    assert ctx.publisher_for_url("https://other.com/a") is None
    ctx.source_status = SourceStatus.CONFIRMED
    assert not ctx.source_confirmed  # needs the selected article too
    ctx.top_article = article("t")
    assert ctx.source_confirmed
