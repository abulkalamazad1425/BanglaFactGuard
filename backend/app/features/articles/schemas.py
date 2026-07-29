"""
app/features/articles/schemas.py
=================================
Pydantic schemas for the articles feature.

Migrated from: app/schemas/article.py
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, computed_field

from app.core.constants import ExtractionMethod, SearchProvider


class ExtractedContentSchema(BaseModel):
    """Raw text content extracted from a single article URL by Stage 6."""

    url: str = Field(..., description="Source URL of the fetched article")
    title: str | None = Field(default=None, description="Extracted article title")
    body: str | None = Field(default=None, description="Extracted main body text")
    author: str | None = Field(default=None, description="Author byline if detected")
    published_date: date | None = Field(default=None)
    extraction_method: ExtractionMethod | None = Field(default=None)
    success: bool = Field(default=False)
    error_message: str | None = Field(default=None)

    @computed_field
    @property
    def word_count(self) -> int:
        if not self.body:
            return 0
        return len(self.body.split())

    @computed_field
    @property
    def char_count(self) -> int:
        return len(self.body) if self.body else 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.prothomalo.com/bangladesh/article/12345",
                "title": "বাংলাদেশে নতুন আইন পাস",
                "body": "জাতীয় সংসদে আজ একটি গুরুত্বপূর্ণ আইন পাস হয়েছে...",
                "author": "নিজস্ব প্রতিবেদক",
                "published_date": "2024-03-15",
                "extraction_method": "trafilatura",
                "success": True,
                "error_message": None,
            }
        }
    }


class CandidateArticleSchema(BaseModel):
    """A candidate article URL returned by a search provider (Stage 5 output)."""

    url: str = Field(..., description="Full URL of the candidate article")
    title_snippet: str | None = Field(default=None)
    search_provider: SearchProvider
    query_type: str
    position: int = Field(default=1, ge=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.prothomalo.com/bangladesh/article/12345",
                "title_snippet": "বাংলাদেশে নতুন আইন পাস - প্রথম আলো",
                "search_provider": "google_rss",
                "query_type": "headline",
                "position": 1,
            }
        }
    }


class RankedArticleSchema(BaseModel):
    """A candidate article that has been extracted (Stage 6) and ranked (Stage 7)."""

    url: str = Field(..., description="Source URL of the article")
    title: str | None = Field(default=None)
    body: str | None = Field(default=None)
    author: str | None = Field(default=None)
    published_date: date | None = Field(default=None)
    rank_score: float = Field(default=0.0, ge=0.0, le=1.0)
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
                "search_provider": "google_rss",
                "extraction_method": "trafilatura",
            }
        }
    }


class ArticleExtractionResult(BaseModel):
    """Wrapper returned by Stage 6 for the full batch of article extraction results."""

    successful: list[ExtractedContentSchema] = Field(default_factory=list)
    failed_urls: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_attempted(self) -> int:
        return len(self.successful) + len(self.failed_urls)

    @computed_field
    @property
    def success_rate(self) -> float:
        if self.total_attempted == 0:
            return 0.0
        return len(self.successful) / self.total_attempted

    model_config = {
        "json_schema_extra": {
            "example": {
                "successful": [],
                "failed_urls": ["https://example.com/article/broken"],
            }
        }
    }

