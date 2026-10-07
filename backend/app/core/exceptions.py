from __future__ import annotations

from typing import Any


class BanglaFactGuardError(Exception):

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


class DomainValidationError(BanglaFactGuardError):

    http_status_code = 422


class SourceNotFoundError(BanglaFactGuardError):

    http_status_code = 404

    def __init__(self, claimed_source: str) -> None:
        super().__init__(
            message=f"Source could not be resolved: {claimed_source!r}",
            details={"claimed_source": claimed_source},
        )
        self.claimed_source = claimed_source


class ImageStorageUnavailableError(BanglaFactGuardError):
    """The card image could not be stored. A photo-card submission is only
    acknowledged once its image bytes are durably stored (the background job
    reads them back), so this is a 503 rather than an accepted submission."""

    http_status_code = 503

    def __init__(self) -> None:
        super().__init__(
            message="The image could not be stored right now. Please try again shortly."
        )


class PermanentJobError(BanglaFactGuardError):
    """A background job failed in a way retrying cannot fix (unreadable
    image, unresolvable source, ...). Carries a user-presentable reason that
    is stored on the submission and shown on its result page."""

    http_status_code = 422

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=reason, details=details)
        self.reason = reason


class PipelineError(BanglaFactGuardError):

    http_status_code = 500


class StageError(PipelineError):

    def __init__(
        self,
        stage_id: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)
        self.stage_id = stage_id


class NormalizationError(StageError):
    pass


class QueryGenerationError(StageError):
    pass


class ClassificationError(StageError):
    pass


class PersistenceError(StageError):
    pass


class RepositoryError(BanglaFactGuardError):

    http_status_code = 500


class RecordNotFoundError(RepositoryError):

    http_status_code = 404

    def __init__(self, model: str, identifier: str) -> None:
        super().__init__(
            message=f"{model} with identifier {identifier!r} was not found.",
            details={"model": model, "identifier": identifier},
        )
        self.model = model
        self.identifier = identifier


class DuplicateRecordError(RepositoryError):

    http_status_code = 409

    def __init__(self, model: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{model} already exists with {field}={value!r}.",
            details={"model": model, "field": field, "value": value},
        )


class ExternalAPIError(BanglaFactGuardError):

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


class PyGoogleNewsError(ExternalAPIError):

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(
            provider="py_google_news", message=message, status_code=status_code
        )


class MLModelError(BanglaFactGuardError):

    http_status_code = 500


class ModelNotLoadedError(MLModelError):

    def __init__(self, model_name: str) -> None:
        super().__init__(
            message=f"ML model {model_name!r} has not been loaded. "
            "Ensure it is initialised in the FastAPI lifespan handler.",
            details={"model_name": model_name},
        )
        self.model_name = model_name


class InferenceError(MLModelError):

    def __init__(self, model_name: str, cause: str) -> None:
        super().__init__(
            message=f"Inference failed for model {model_name!r}: {cause}",
            details={"model_name": model_name, "cause": cause},
        )
        self.model_name = model_name


class AuthError(BanglaFactGuardError):

    http_status_code = 401


class InvalidCredentialsError(AuthError):

    def __init__(self) -> None:
        super().__init__(
            message="Invalid email or password.",
            details={},
        )


class TokenExpiredError(AuthError):

    def __init__(self) -> None:
        super().__init__(message="Authentication token has expired.")


class TokenInvalidError(AuthError):

    def __init__(self) -> None:
        super().__init__(message="Authentication token is invalid.")


class OtpInvalidError(AuthError):

    def __init__(self) -> None:
        super().__init__(message="Invalid or expired verification code.")


class OtpGenerationError(BanglaFactGuardError):

    http_status_code = 503

    def __init__(self) -> None:
        super().__init__(
            message="Could not generate a verification code. Please try again."
        )


class EmailDeliveryError(BanglaFactGuardError):

    http_status_code = 503

    def __init__(self) -> None:
        super().__init__(
            message="We couldn't send the verification email right now. "
            "Please try again in a few minutes."
        )


class InactiveAccountError(AuthError):

    http_status_code = 403

    def __init__(self) -> None:
        super().__init__(message="This account has been deactivated.")


class PermissionDeniedError(BanglaFactGuardError):

    http_status_code = 403

    def __init__(self, required_role: str | None = None) -> None:
        msg = "You do not have permission to perform this action."
        if required_role:
            msg += f" Required role: {required_role}."
        super().__init__(message=msg, details={"required_role": required_role})


class WeakPasswordError(BanglaFactGuardError):

    http_status_code = 422

    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Password does not meet requirements: {reason}",
            details={"reason": reason},
        )
