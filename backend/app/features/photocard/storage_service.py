"""
MinIO object storage for uploaded photo cards.

Kept separate from the multimodal storage service so photo-card images land
under their own ``photocard/`` prefix and can be retained, expired or audited
independently of multimodal submission images.

Failures are reported to the caller (False / None) rather than raised. The
caller decides what they mean: an image that cannot be stored is not accepted
(`ImageStorageUnavailableError`, 503), because the background job reads the
card back from storage; a missing preview URL only hides the thumbnail.
"""

from __future__ import annotations

import asyncio
import io
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import structlog
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_MINIO_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="photocard-minio")

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")

_CONTENT_TYPES = {
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class PhotoCardStorageService:
    """Stores photo-card images and issues short-lived preview URLs."""

    def __init__(self) -> None:
        config = _SETTINGS.minio
        self._client = Minio(
            endpoint=config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self._bucket = config.bucket_name
        self._url_expiry = config.presigned_url_expiry_seconds

    async def ensure_bucket(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_MINIO_POOL, self._ensure_bucket_sync)
        logger.info("photocard_bucket_ready", bucket=self._bucket)

    def _ensure_bucket_sync(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def build_object_key(self, submission_id: uuid.UUID, filename: str) -> str:
        safe_name = _SAFE_FILENAME_RE.sub("_", filename)[:128] or "photocard.jpg"
        return f"photocard/{submission_id}/{safe_name}"

    async def upload(
        self, image_bytes: bytes, object_key: str
    ) -> bool:
        """Upload the card. Returns ``False`` when storage is unavailable."""
        content_type = _infer_content_type(object_key)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                _MINIO_POOL,
                lambda: self._client.put_object(
                    bucket_name=self._bucket,
                    object_name=object_key,
                    data=io.BytesIO(image_bytes),
                    length=len(image_bytes),
                    content_type=content_type,
                ),
            )
            logger.info(
                "photocard_image_uploaded",
                key=object_key,
                size_bytes=len(image_bytes),
            )
            return True
        except (S3Error, OSError, ValueError) as exc:
            logger.warning(
                "photocard_image_upload_failed", key=object_key, error=str(exc)
            )
            return False

    async def download(self, object_key: str) -> bytes | None:
        """Fetch the stored card. The background job reads the image from
        here rather than from the (long gone) upload request."""
        loop = asyncio.get_running_loop()

        def _get() -> bytes:
            response = self._client.get_object(self._bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await loop.run_in_executor(_MINIO_POOL, _get)
        except (S3Error, OSError, ValueError) as exc:
            logger.warning("photocard_image_download_failed", key=object_key, error=str(exc))
            return None

    async def get_presigned_url(self, object_key: str) -> str | None:
        """Short-lived preview URL, or ``None`` when it cannot be issued."""
        if not object_key:
            return None
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                _MINIO_POOL,
                lambda: self._client.presigned_get_object(
                    bucket_name=self._bucket,
                    object_name=object_key,
                    expires=timedelta(seconds=self._url_expiry),
                ),
            )
        except (S3Error, OSError, ValueError) as exc:
            logger.warning(
                "photocard_presigned_url_failed", key=object_key, error=str(exc)
            )
            return None


def _infer_content_type(name: str) -> str:
    lowered = name.lower()
    for suffix, content_type in _CONTENT_TYPES.items():
        if lowered.endswith(suffix):
            return content_type
    return "application/octet-stream"
