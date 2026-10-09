"""Card images under their own prefix; storage trouble is reported (False /
None), never raised - the caller decides what it means."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.features.photocard import storage_service as module
from app.features.photocard.storage_service import PhotoCardStorageService


@pytest.fixture
def minio(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(module, "Minio", lambda **kw: client)
    return client


async def test_keys_content_types_and_round_trip(minio):
    svc = PhotoCardStorageService()
    sid = uuid.uuid4()
    assert svc.build_object_key(sid, "../My Card!.WEBP") == f"photocard/{sid}/.._My_Card_.WEBP"
    assert svc.build_object_key(sid, "") == f"photocard/{sid}/photocard.jpg"
    assert await svc.upload(b"img", "photocard/x/card.jpeg")
    assert minio.put_object.call_args.kwargs["content_type"] == "image/jpeg"
    await svc.upload(b"img", "photocard/x/card")
    assert minio.put_object.call_args.kwargs["content_type"] == "application/octet-stream"
    response = MagicMock(read=MagicMock(return_value=b"img"))
    minio.get_object.return_value = response
    assert await svc.download("k") == b"img" and response.release_conn.called
    minio.presigned_get_object.return_value = "https://minio/signed"
    assert await svc.get_presigned_url("k") == "https://minio/signed" and await svc.get_presigned_url("") is None
    minio.bucket_exists.return_value = False
    await svc.ensure_bucket()
    minio.make_bucket.assert_called_once()


async def test_storage_trouble_is_reported_not_raised(minio):
    for name in ("put_object", "get_object", "presigned_get_object"):
        getattr(minio, name).side_effect = OSError("minio down")
    svc = PhotoCardStorageService()
    assert await svc.upload(b"img", "k.png") is False
    assert await svc.download("k") is None and await svc.get_presigned_url("k") is None
