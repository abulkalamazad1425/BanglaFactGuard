"""
app/models/__init__.py
=======================
Re-exports all ORM models from a single import point.

IMPORTANT: This file must import every model class so that SQLAlchemy's
`MetaData` object (on `Base`) is populated before Alembic runs
`Base.metadata.create_all()` or generates migration scripts.

If a model is not imported here, Alembic will not detect it and will
generate DROP TABLE statements for existing tables on the next migration.

Usage in Alembic env.py::

    from app.models import Base  # noqa: F401 — triggers all model imports
    target_metadata = Base.metadata
"""

from app.models.base import Base  # noqa: F401
from app.models.retrieved_article import RetrievedArticle  # noqa: F401
from app.models.search_query import SearchQuery  # noqa: F401
from app.models.source_registry import SourceRegistry  # noqa: F401
from app.models.verification_log import VerificationLog  # noqa: F401
from app.models.verification_result import VerificationResult  # noqa: F401
from app.models.verified_claim import VerifiedClaim  # noqa: F401

__all__ = [
    "Base",
    "SourceRegistry",
    "VerifiedClaim",
    "SearchQuery",
    "RetrievedArticle",
    "VerificationResult",
    "VerificationLog",
]
