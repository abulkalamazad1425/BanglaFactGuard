"""Pipeline article DTOs: search candidates (S04) and extracted, ranked
articles (S06/S07; also returned as `matched_articles`)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field

from app.core.constants import ExtractionMethod, SearchProvider


class CandidateArticleSchema(BaseModel):
    """A candidate article URL returned by a search provider (Stage 5 output)."""

    url: str = Field(..., description="Full URL of the candidate article")
    title_snippet: str | None = Field(default=None)
    search_provider: SearchProvider
    query_type: str
    position: int = Field(default=1, ge=1)


class RankedArticleSchema(BaseModel):
    """A candidate article that has been extracted (Stage 6) and ranked (Stage 7)."""

    url: str = Field(..., description="Source URL of the article")
    title: str | None = Field(default=None)
    body: str | None = Field(default=None)
    author: str | None = Field(default=None)
    published_date: date | None = Field(default=None)
    published_at: datetime | None = Field(
        default=None,
        description="datePublished with time, tz-aware (Asia/Dhaka), when the page carried one.",
    )
    published_date_source: str | None = Field(
        default=None,
        description="Provenance of published_date (json_ld.datePublished, meta.article:published_time, selector, ...). Never dateModified or a crawl date.",
    )
    published_tz_assumed: bool = Field(
        default=False,
        description="True when the page's timestamp had no UTC offset and Asia/Dhaka was assumed.",
    )
    rank_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Retrieval relevance (is this the report the claim is about?). NOT a content-match score.",
    )
    search_provider: SearchProvider
    extraction_method: ExtractionMethod | None = Field(default=None)

    @computed_field
    @property
    def has_body(self) -> bool:
        return bool(self.body and len(self.body.strip()) > 50)

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.prothomalo.com/bangladesh/article/12345",
                "title": "বাংলাদেশে নতুন আইন পাস",
                "body": "জাতীয় সংসদে আজ একটি গুরুত্বপূর্ণ আইন পাস হয়েছে...",
                "author": "নিজস্ব প্রতিবেদক",
                "published_date": "2024-03-15",
                "rank_score": 0.87,
                "search_provider": "py_google_news",
                "extraction_method": "trafilatura",
            }
        }
    }

