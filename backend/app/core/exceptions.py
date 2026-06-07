"""
app/core/exceptions.py
======================
Domain exception hierarchy for BanglaFactGuard.

Design decisions:
- All exceptions inherit from a single `BanglaFactGuardError` base so that
  global exception handlers can catch the entire domain with one clause.
- Each exception carries a `message`, optional `details` dict, and an
  `http_status_code` class attribute — allowing the FastAPI exception handler
  to map exceptions to HTTP responses without any if/elif chains.
- Exceptions are intentionally thin value objects (no business logic) so
  they can be safely imported from any layer without introducing coupling.

Exception hierarchy:
    BanglaFactGuardError
    ├── ConfigurationError
    ├── ValidationError (domain — not Pydantic's)
    ├── SourceNotFoundError
    ├── SourceNormalizationError
    ├── PipelineError
    │   ├── StageError
    │   │   ├── NormalizationError
    │   │   ├── CacheError
    │   │   ├── QueryGenerationError
    │   │   ├── SearchError
    │   │   ├── ExtractionError
    │   │   ├── SimilarityError
    │   │   ├── NLIError
    │   │   └── ClassificationError
    ├── RepositoryError
    │   ├── RecordNotFoundError
    │   └── DuplicateRecordError
    ├── CacheBackendError
    ├── ExternalAPIError
    │   ├── BraveAPIError
    │   ├── GoogleRSSError
    │   └── DDGError
    └── MLModelError
        ├── ModelNotLoadedError
        └── InferenceError
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class BanglaFactGuardError(Exception):
    """
    Base exception for all domain-level errors in BanglaFactGuard.

    Attributes:
        message:     Human-readable error description.
        details:     Optional structured context (logged, never returned raw to clients).
        http_status_code: Default HTTP status for FastAPI exception handlers.
    """

    http_status_code: int = 500

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigurationError(BanglaFactGuardError):
    """Raised when required configuration values are missing or invalid."""

    http_status_code = 500


# ---------------------------------------------------------------------------
# Domain Validation
# ---------------------------------------------------------------------------


class DomainValidationError(BanglaFactGuardError):
    """
    Raised when incoming request data fails domain-level validation
    (as opposed to Pydantic schema validation which happens earlier).
    """

    http_status_code = 422


# ---------------------------------------------------------------------------
# Source Resolution
# ---------------------------------------------------------------------------


class SourceNotFoundError(BanglaFactGuardError):
    """
    Raised when a claimed source cannot be resolved to a known canonical domain,
    either via the static alias map or the source_registry table.
    """

    http_status_code = 404

    def __init__(self, claimed_source: str) -> None:
        super().__init__(
            message=f"Source could not be resolved: {claimed_source!r}",
            details={"claimed_source": claimed_source},
        )
        self.claimed_source = claimed_source


class SourceNormalizationError(BanglaFactGuardError):
    """Raised when source normalisation fails due to an unexpected input format."""

    http_status_code = 422


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineError(BanglaFactGuardError):
    """
    Raised when the verification pipeline encounters an unrecoverable error.
    Individual stage failures that degrade gracefully should raise StageError
    and be caught by the orchestrator rather than propagating as PipelineError.
    """

    http_status_code = 500


class StageError(PipelineError):
    """
    Raised by a pipeline stage when it cannot complete its work.

    Attributes:
        stage_id: The PipelineStageID enum value identifying the failing stage.
    """

    def __init__(
        self,
        stage_id: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.stage_id = stage_id


class NormalizationError(StageError):
    """Raised by S01 when Bangla/Unicode normalisation fails."""


class CacheError(StageError):
    """Raised by S02 when the cache layer throws an unexpected error."""


class QueryGenerationError(StageError):
    """Raised by S03 when query generation produces no usable queries."""


class SearchError(StageError):
    """Raised by S04 when all search providers are exhausted or fail."""


class ExtractionError(StageError):
    """Raised by S06 when article content cannot be extracted from a URL."""


class SimilarityError(StageError):
    """Raised by S08 when similarity computation fails entirely."""


class NLIError(StageError):
    """Raised by S09 when the NLI model produces an unexpected output."""


class ClassificationError(StageError):
    """Raised by S11 when classification rules cannot produce a verdict."""


class PersistenceError(StageError):
    """Raised by S12 when database writes fail and the result cannot be stored."""


# ---------------------------------------------------------------------------
# Repository / Database
# ---------------------------------------------------------------------------


class RepositoryError(BanglaFactGuardError):
    """Base class for database access errors."""

    http_status_code = 500


class RecordNotFoundError(RepositoryError):
    """Raised when a requested DB record does not exist."""

    http_status_code = 404

    def __init__(self, model: str, identifier: str) -> None:
        super().__init__(
            message=f"{model} with identifier {identifier!r} was not found.",
            details={"model": model, "identifier": identifier},
        )
        self.model = model
        self.identifier = identifier


class DuplicateRecordError(RepositoryError):
    """Raised when a unique-constraint violation occurs on insert."""

    http_status_code = 409

    def __init__(self, model: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{model} already exists with {field}={value!r}.",
            details={"model": model, "field": field, "value": value},
        )


# ---------------------------------------------------------------------------
# Cache Backend
# ---------------------------------------------------------------------------


class CacheBackendError(BanglaFactGuardError):
    """
    Raised when Redis is unavailable or returns an unexpected error.
    The pipeline treats this as a warning and falls through to the DB / full pipeline.
    """

    http_status_code = 503


# ---------------------------------------------------------------------------
# External API Clients
# ---------------------------------------------------------------------------


class ExternalAPIError(BanglaFactGuardError):
    """Base class for errors from third-party search API clients."""

    http_status_code = 502

    def __init__(
        self,
        provider: str,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details or {})
        self.provider = provider
        self.upstream_status_code = status_code
        self.details["provider"] = provider
        if status_code is not None:
            self.details["upstream_status_code"] = status_code


class BraveAPIError(ExternalAPIError):
    """Raised when the Brave Search API request fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(provider="brave", message=message, status_code=status_code)


class GoogleRSSError(ExternalAPIError):
    """Raised when Google News RSS parsing or fetching fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(provider="google_rss", message=message, status_code=status_code)


class DDGError(ExternalAPIError):
    """Raised when the DuckDuckGo fallback search fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(provider="ddg", message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# ML Model
# ---------------------------------------------------------------------------


class MLModelError(BanglaFactGuardError):
    """Base class for machine-learning model errors."""

    http_status_code = 500


class ModelNotLoadedError(MLModelError):
    """
    Raised when a model is accessed before it has been loaded into
    application state (should never happen in production after lifespan init).
    """

    def __init__(self, model_name: str) -> None:
        super().__init__(
            message=f"ML model {model_name!r} has not been loaded. "
                    "Ensure it is initialised in the FastAPI lifespan handler.",
            details={"model_name": model_name},
        )
        self.model_name = model_name


class InferenceError(MLModelError):
    """Raised when a model inference call raises an unexpected exception."""

    def __init__(self, model_name: str, cause: str) -> None:
        super().__init__(
            message=f"Inference failed for model {model_name!r}: {cause}",
            details={"model_name": model_name, "cause": cause},
        )
        self.model_name = model_name
