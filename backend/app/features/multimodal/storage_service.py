
from __future__ import annotations

import asyncio
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

import structlog
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.exceptions import BanglaFactGuardError

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_MINIO_POOL = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="minio-io",
)

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


def _sanitise_filename(name: str) -> str:
    safe = _SAFE_FILENAME_RE.sub("_", name)
    return safe[:128]


class MultimodalStorageError(BanglaFactGuardError):
    http_status_code = 502


class MultimodalStorageService:

    def __init__(self) -> None:
        cfg = _SETTINGS.minio
        self._client = Minio(
            endpoint=cfg.endpoint,
            access_key=cfg.access_key,
            secret_key=cfg.secret_key,
            secure=cfg.secure,
        )
        self._bucket = cfg.bucket_name
        self._url_expiry = cfg.presigned_url_expiry_seconds





    async def ensure_bucket(self) -> None:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(_MINIO_POOL, self._ensure_bucket_sync)
            logger.info("minio_bucket_ready", bucket=self._bucket)
        except S3Error as exc:
            logger.error("minio_bucket_create_failed", bucket=self._bucket, error=str(exc))
            raise MultimodalStorageError(
                message=f"Failed to create MinIO bucket '{self._bucket}': {exc}",
                details={"bucket": self._bucket, "error": str(exc)},
            ) from exc

    def _ensure_bucket_sync(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)





    async def upload_image(
        self,
        image_bytes: bytes,
        original_filename: str,
        *,
        submission_id: str | None = None,
    ) -> str:
        sid = submission_id or str(uuid.uuid4())
        safe_name = _sanitise_filename(original_filename)
        object_key = f"multimodal/{sid}/{safe_name}"

        import io
        data_stream = io.BytesIO(image_bytes)
        content_type = _infer_content_type(original_filename)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                _MINIO_POOL,
                lambda: self._client.put_object(
                    bucket_name=self._bucket,
                    object_name=object_key,
                    data=data_stream,
                    length=len(image_bytes),
                    content_type=content_type,
                ),
            )
            logger.info(
                "minio_image_uploaded",
                key=object_key,
                size_bytes=len(image_bytes),
                content_type=content_type,
            )
            return object_key
        except S3Error as exc:
            logger.error("minio_upload_failed", key=object_key, error=str(exc))
            raise MultimodalStorageError(
                message=f"Image upload to MinIO failed: {exc}",
                details={"object_key": object_key, "error": str(exc)},
            ) from exc





    async def get_presigned_url(self, object_key: str) -> str:
        from datetime import timedelta

        loop = asyncio.get_event_loop()
        try:
            url: str = await loop.run_in_executor(
                _MINIO_POOL,
                lambda: self._client.presigned_get_object(
                    bucket_name=self._bucket,
                    object_name=object_key,
                    expires=timedelta(seconds=self._url_expiry),
                ),
            )
            return url
        except S3Error as exc:
            logger.warning("minio_presigned_url_failed", key=object_key, error=str(exc))
            raise MultimodalStorageError(
                message=f"Failed to generate pre-signed URL: {exc}",
                details={"object_key": object_key},
            ) from exc





    async def delete_image(self, object_key: str) -> None:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                _MINIO_POOL,
                lambda: self._client.remove_object(self._bucket, object_key),
            )
            logger.info("minio_image_deleted", key=object_key)
        except Exception as exc:
            logger.warning("minio_delete_failed", key=object_key, error=str(exc))







def _infer_content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"
