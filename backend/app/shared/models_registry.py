"""
app/shared/models_registry.py
==============================
Central registry of all ORM models.

IMPORTANT: This file must import every model class so that SQLAlchemy's
MetaData object (on Base) is fully populated before Alembic runs
`Base.metadata.create_all()` or generates migration scripts.

All feature models are imported here. If a model is not imported here,
Alembic will not detect it and may generate DROP TABLE statements.

Usage in Alembic env.py::

    from app.shared.models_registry import Base  # noqa: F401
    target_metadata = Base.metadata
"""

from app.shared.base_model import Base  # noqa: F401

# Verification feature
from app.features.verification.models import (  # noqa: F401
    VerifiedClaim,
    VerificationResult,
    VerificationLog,
)

# Articles feature
from app.features.articles.models import (  # noqa: F401
    RetrievedArticle,
    SearchQuery,
)

# Sources feature
from app.features.sources.models import VerifiedSource  # noqa: F401

# Auth feature
from app.features.auth.models import (  # noqa: F401
    User,
    RefreshToken,
    PasswordResetToken,
)

# Users feature
from app.features.users.models import UserProfile  # noqa: F401

# Expert review feature
from app.features.expert_review.models import ExpertReview  # noqa: F401

# Multimodal feature
from app.features.multimodal.models import (  # noqa: F401
    MultimodalSubmission,
    MediaAnalysisResult,
)

# Notifications feature
from app.features.notifications.models import Notification  # noqa: F401

# User feedback feature
from app.features.feedback.models import UserFeedback  # noqa: F401


__all__ = [
    "Base",
    # Verification
    "VerifiedClaim",
    "VerificationResult",
    "VerificationLog",
    # Articles
    "RetrievedArticle",
    "SearchQuery",
    # Sources
    "VerifiedSource",
    # Auth
    "User",
    "RefreshToken",
    "PasswordResetToken",
    # Users
    "UserProfile",
    # Expert review
    "ExpertReview",
    # Multimodal
    "MultimodalSubmission",
    "MediaAnalysisResult",
    # Notifications
    "Notification",
    # Feedback
    "UserFeedback",
]
