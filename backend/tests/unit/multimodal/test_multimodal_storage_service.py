"""MinIO image storage: safe object keys, the right content type, and storage
errors surfaced as a typed 502 error."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from minio.error import S3Error

from app.features.multimodal import storage_service as module
from app.features.multimodal.storage_service import MultimodalStorageError, MultimodalStorageService


def s3_error() -> S3Error:
    return S3Error(MagicMock(), "AccessDenied", "denied", "res", "req", "host")


@pytest.fixture
def minio(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(module, "Minio", lambda **kw: client)
    return client


async def test_upload_uses_a_safe_key_and_the_right_content_type(minio):
    svc = MultimodalStorageService()
    key = await svc.upload_image(b"img", "../my card (1).PNG", submission_id="sid")
    assert key == "multimodal/sid/.._my_card__1_.PNG"
    kwargs = minio.put_object.call_args.kwargs
    assert (kwargs["object_name"], kwargs["content_type"], kwargs["length"]) == (key, "image/png", 3)
    for name, kind in (("a.jpeg", "image/jpeg"), ("a.webp", "image/webp"), ("a.gif", "image/gif"), ("a.bin", "application/octet-stream")):
        await svc.upload_image(b"x", name)
        assert minio.put_object.call_args.kwargs["content_type"] == kind
    assert (await svc.upload_image(b"x", "a.png")).startswith("multimodal/")  # a generated id when none is given


async def test_bucket_urls_reads_and_deletes(minio):
    svc = MultimodalStorageService()
    minio.bucket_exists.return_value = False
    await svc.ensure_bucket()
    minio.make_bucket.assert_called_once()
    minio.presigned_get_object.return_value = "https://minio/signed"
    assert await svc.get_presigned_url("k") == "https://minio/signed"
    response = MagicMock(read=MagicMock(return_value=b"bytes"))
    minio.get_object.return_value = response
    assert await svc.read_image("k") == b"bytes"
    response.release_conn.assert_called_once()
    minio.remove_object.side_effect = RuntimeError("gone")
    await svc.delete_image("k")  # cleanup never raises


@pytest.mark.parametrize("method,args", [
    ("ensure_bucket", ()), ("upload_image", (b"x", "a.png")), ("get_presigned_url", ("k",)),
])
async def test_storage_failures_are_typed_errors(minio, method, args):
    for name in ("bucket_exists", "put_object", "presigned_get_object"):
        getattr(minio, name).side_effect = s3_error()
    with pytest.raises(MultimodalStorageError):
        await getattr(MultimodalStorageService(), method)(*args)
