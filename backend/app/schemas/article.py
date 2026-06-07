"""
app/schemas/article.py
=======================
Pydantic schemas for article retrieval, extraction, and ranking stages
(Stages 5–7) of the verification pipeline.

Schema hierarchy:
    ExtractedContentSchema          Raw extraction output from trafilatura/BS4
         │
    CandidateArticleSchema          URL + metadata before ranking (Stage 5 output)
         │
    RankedArticleSchema             Ranked candidate with score (Stage 7 output)
         │
    ArticleExtractionResult         Full extraction + ranking result (Stage 6+7 combined)

Design decisions:
- Schemas are intentionally flat (no nesting beyond scores) to simplify
  serialisation and Redis caching (JSON strings, not nested objects).
- `url` uses `AnyHttpUrl` for strict validation. During extraction, invalid
  URLs are rejected early before an HTTP fetch is attempted.
- All extracted text fields are `str | None` because extraction may partially
  succeed (e.g. title extracted but body empty) — the pipeline handles this
  gracefully rather than discarding the article entirely.
- `published_date` is `date | None` (not datetime) because many Bangla news
  sites only expose date granularity in their HTML metadata.
- `word_count` is a derived convenience field computed at extraction time;
  it avoids repeated `len(body.split())` calls in downstream stages.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import AnyHttpUrl, BaseModel, Field, computed_field, model_validator

from app.core.constants import ExtractionMethod, SearchProvider


class ExtractedContentSchema(BaseModel):
    """
    Raw text content extracted from a single article URL by Stage 6.

    This schema represents the immediate output of the article extractor
    (trafilatura primary, BeautifulSoup fallback). It does NOT include
    ranking scores — those are added in Stage 7.

    Attributes:
        url:               The source URL that was fetched.
        title:             Extracted article title / <h1> text.
        body:              Extracted full article body (main content only,
                           no navigation/ads).
        author:            Byline if detectable in metadata.
        published_date:    Publication date if parseable from article metadata.
        extraction_method: Which backend produced this content.
        success:           False if extraction failed or body is below min length.
        error_message:     Populated when success=False to record failure reason.
    """

    url: str = Field(..., description="Source URL of the fetched article")
    title: str | None = Field(default=None, description="Extracted article title")
    body: str | None = Field(default=None, description="Extracted main body text")
    author: str | None = Field(default=None, description="Author byline if detected")
    published_date: date | None = Field(
        default=None,
        description="Publication date extracted from article metadata (date only, no time)",
    )
    extraction_method: ExtractionMethod | None = Field(
        default=None,
        description="Which extraction backend was used: trafilatura | beautifulsoup",
    )
    success: bool = Field(
        default=False,
        description="True if extraction produced usable content above minimum length",
    )
    error_message: str | None = Field(
        default=None,
        description="Failure reason when success=False",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        """Approximate word count of the extracted body (0 if body is None)."""
        if not self.body:
            return 0
        return len(self.body.split())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def char_count(self) -> int:
        """Character count of the extracted body (0 if body is None)."""
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
    """
    A candidate article URL returned by a search provider (Stage 5 output).

    At this stage, only the URL, title snippet (from search result), and
    source metadata are known. Full content has not yet been extracted.

    Attributes:
        url:             Full URL of the candidate article.
        title_snippet:   Short title or snippet from the search result (not the full article title).
        search_provider: Which provider returned this result.
        query_type:      Which query variant surfaced this result.
        position:        Rank position within the search result list (1-based).
    """

    url: str = Field(..., description="Full URL of the candidate article")
    title_snippet: str | None = Field(
        default=None,
        description="Title or snippet as returned by the search provider",
    )
    search_provider: SearchProvider = Field(
        ...,
        description="Which search provider returned this candidate",
    )
    query_type: str = Field(
        ...,
        description="Query variant that surfaced this candidate (headline, keywords, etc.)",
    )
    position: int = Field(
        default=1,
        ge=1,
        description="Position in the search result list (1 = top result)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.prothomalo.com/bangladesh/article/12345",
                "title_snippet": "বাংলাদেশে নতুন আইন পাস - প্রথম আলো",
                "search_provider": "brave",
                "query_type": "headline",
                "position": 1,
            }
        }
    }


class RankedArticleSchema(BaseModel):
    """
    A candidate article that has been both extracted (Stage 6) and ranked
    (Stage 7). This is the primary evidence unit passed to Stages 8–10.

    Combines the raw search-result metadata (CandidateArticleSchema) with
    the extracted content (ExtractedContentSchema) and the Stage 7 rank score.

    Attributes:
        url:          Source URL.
        title:        Extracted article title.
        body:         Extracted article body.
        author:       Author byline.
        published_date: Publication date.
        rank_score:   Stage 7 composite ranking score in [0.0, 1.0].
                      Higher = more likely to be the matching article.
        search_provider: Which provider originally returned this URL.
        extraction_method: Which extractor was used.
    """

    url: str = Field(..., description="Source URL of the article")
    title: str | None = Field(default=None, description="Extracted article title")
    body: str | None = Field(default=None, description="Extracted article body text")
    author: str | None = Field(default=None, description="Author byline if available")
    published_date: date | None = Field(
        default=None,
        description="Publication date (date only)",
    )
    rank_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Stage 7 composite ranking score [0, 1] — higher = more relevant",
    )
    search_provider: SearchProvider = Field(
        ...,
        description="Search provider that originally returned this URL",
    )
    extraction_method: ExtractionMethod | None = Field(
        default=None,
        description="Extraction backend used for content retrieval",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_body(self) -> bool:
        """True if this article has extractable body content."""
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
                "search_provider": "brave",
                "extraction_method": "trafilatura",
            }
        }
    }


class ArticleExtractionResult(BaseModel):
    """
    Wrapper returned by Stage 6 for the full batch of article extraction
    results for a single claim.

    Carries both the successfully extracted articles and a list of URLs
    that failed extraction, so the pipeline can log failures without losing
    partial results.

    Attributes:
        successful:          List of successfully extracted articles (may be empty).
        failed_urls:         URLs where extraction failed (for logging/audit).
        total_attempted:     Total number of URLs attempted.
    """

    successful: list[ExtractedContentSchema] = Field(
        default_factory=list,
        description="Successfully extracted article contents",
    )
    failed_urls: list[str] = Field(
        default_factory=list,
        description="URLs where extraction failed (both trafilatura and BS4)",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_attempted(self) -> int:
        """Total URLs attempted = successful + failed."""
        return len(self.successful) + len(self.failed_urls)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Fraction of URLs successfully extracted (0.0–1.0)."""
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
