"""
app/schemas/__init__.py
========================
Re-exports all public Pydantic schemas for convenient single-import access.

Design rule: schemas NEVER import from `app/models/` (ORM layer).
The direction of dependency is always:
    API Layer → Schemas → Core (constants, exceptions)

This prevents circular imports and keeps the schema layer independently
testable without a database connection.
"""

from app.schemas.article import (
    ArticleExtractionResult,
    CandidateArticleSchema,
    ExtractedContentSchema,
    RankedArticleSchema,
)
from app.schemas.scores import ManipulationFlagsSchema, VerificationScoresSchema
from app.schemas.source import (
    SourceCreateSchema,
    SourceListSchema,
    SourceResponseSchema,
    SourceUpdateSchema,
)
from app.schemas.verification import (
    VerificationRequest,
    VerificationResponse,
    VerificationResultSummary,
    VerificationStatusResponse,
)

__all__ = [
    # Verification
    "VerificationRequest",
    "VerificationResponse",
    "VerificationResultSummary",
    "VerificationStatusResponse",
    # Scores
    "VerificationScoresSchema",
    "ManipulationFlagsSchema",
    # Articles
    "ExtractedContentSchema",
    "CandidateArticleSchema",
    "RankedArticleSchema",
    "ArticleExtractionResult",
    # Sources
    "SourceCreateSchema",
    "SourceUpdateSchema",
    "SourceResponseSchema",
    "SourceListSchema",
]
