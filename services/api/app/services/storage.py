from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import boto3
from botocore.config import Config

from app.core.config import Settings, StorageMode
from app.core.errors import FitCheckError


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    sha256: str
    size: int
    content_type: str
    metadata: Mapping[str, str]


class ObjectStorage(Protocol):
    async def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject: ...

    async def get_bytes(self, key: str) -> bytes: ...

    async def head(self, key: str) -> StoredObject: ...

    async def delete(self, key: str) -> None: ...

    async def signed_read_url(self, key: str, expires_seconds: int | None = None) -> str: ...

    async def signed_upload_url(
        self, key: str, content_type: str, expires_seconds: int | None = None
    ) -> str: ...


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class LocalObjectStorage:
    """Private local filesystem storage used only for mock/demo development."""

    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root.resolve()
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        if key.startswith("/") or ".." in Path(key).parts:
            raise FitCheckError("INVALID_OBJECT_KEY", "The storage object key is invalid.")
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise FitCheckError("INVALID_OBJECT_KEY", "The storage object key is invalid.")
        return path

    async def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        path = self._path_for(key)
        digest = sha256_bytes(content)
        object_metadata = {"sha256": digest, **dict(metadata or {})}

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(f"{path.suffix}.partial")
            temp.write_bytes(content)
            os.replace(temp, path)
            path.with_suffix(f"{path.suffix}.metadata.json").write_text(
                json.dumps(
                    {"content_type": content_type, "metadata": object_metadata},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )

        await asyncio.to_thread(write)
        return StoredObject(key, digest, len(content), content_type, object_metadata)

    async def get_bytes(self, key: str) -> bytes:
        path = self._path_for(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as error:
            raise FitCheckError(
                "OBJECT_NOT_FOUND", "The requested asset is unavailable."
            ) from error

    async def head(self, key: str) -> StoredObject:
        path = self._path_for(key)
        try:
            content = await asyncio.to_thread(path.read_bytes)
            metadata_path = path.with_suffix(f"{path.suffix}.metadata.json")
            raw_metadata = json.loads(
                await asyncio.to_thread(metadata_path.read_text, encoding="utf-8")
            )
        except FileNotFoundError as error:
            raise FitCheckError(
                "OBJECT_NOT_FOUND", "The requested asset is unavailable."
            ) from error
        return StoredObject(
            key=key,
            sha256=raw_metadata["metadata"]["sha256"],
            size=len(content),
            content_type=raw_metadata["content_type"],
            metadata=raw_metadata["metadata"],
        )

    async def delete(self, key: str) -> None:
        """Remove one private mock object and its sidecar metadata idempotently."""

        path = self._path_for(key)

        def remove() -> None:
            path.unlink(missing_ok=True)
            path.with_suffix(f"{path.suffix}.metadata.json").unlink(missing_ok=True)

        await asyncio.to_thread(remove)

    async def signed_read_url(self, key: str, expires_seconds: int | None = None) -> str:
        self._path_for(key)
        # This route is enabled only in local mock mode by app.main.
        return f"{self.public_base_url}/{quote(key, safe='/')}"

    async def signed_upload_url(
        self, key: str, content_type: str, expires_seconds: int | None = None
    ) -> str:
        raise FitCheckError(
            "LOCAL_DIRECT_UPLOAD_UNAVAILABLE",
            (
                "Local mock storage does not issue browser upload URLs. "
                "Upload through the API in development."
            ),
        )


class B2ObjectStorage:
    """Backblaze B2 through its S3-compatible API; all objects remain private."""

    def __init__(self, settings: Settings) -> None:
        if not settings.b2_bucket or settings.b2_key_id is None or settings.b2_app_key is None:
            raise FitCheckError(
                "B2_CONFIGURATION_MISSING",
                "B2 storage needs a bucket and least-privilege server credentials.",
                recommended_action="Configure B2_BUCKET, B2_KEY_ID, and B2_APP_KEY server-side.",
            )
        self.bucket = settings.b2_bucket
        self.default_expiry = settings.b2_presign_expires_seconds
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.b2_endpoint_url or None,
            region_name=settings.b2_region or None,
            aws_access_key_id=settings.b2_key_id.get_secret_value(),
            aws_secret_access_key=settings.b2_app_key.get_secret_value(),
            config=Config(signature_version="s3v4"),
        )

    async def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        digest = sha256_bytes(content)
        object_metadata = {"sha256": digest, **dict(metadata or {})}

        def put_and_verify() -> None:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata=object_metadata,
                ServerSideEncryption="AES256",
            )
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            if response["ContentLength"] != len(content):
                raise FitCheckError(
                    "B2_VALIDATION_FAILED",
                    "Saving securely failed validation.",
                    retryable=True,
                )
            persisted_hash = response.get("Metadata", {}).get("sha256")
            if persisted_hash != digest:
                raise FitCheckError(
                    "B2_VALIDATION_FAILED",
                    "Saving securely failed validation.",
                    retryable=True,
                )

        await asyncio.to_thread(put_and_verify)
        return StoredObject(key, digest, len(content), content_type, object_metadata)

    async def get_bytes(self, key: str) -> bytes:
        def get() -> bytes:
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                return bytes(response["Body"].read())
            except self.client.exceptions.NoSuchKey as error:
                raise FitCheckError(
                    "OBJECT_NOT_FOUND", "The requested asset is unavailable."
                ) from error

        return await asyncio.to_thread(get)

    async def head(self, key: str) -> StoredObject:
        def read_head() -> StoredObject:
            try:
                response = self.client.head_object(Bucket=self.bucket, Key=key)
            except self.client.exceptions.ClientError as error:
                raise FitCheckError(
                    "OBJECT_NOT_FOUND", "The requested asset is unavailable."
                ) from error
            metadata = response.get("Metadata", {})
            return StoredObject(
                key=key,
                sha256=metadata.get("sha256", ""),
                size=response["ContentLength"],
                content_type=response.get("ContentType", "application/octet-stream"),
                metadata=metadata,
            )

        return await asyncio.to_thread(read_head)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def signed_read_url(self, key: str, expires_seconds: int | None = None) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds or self.default_expiry,
        )

    async def signed_upload_url(
        self, key: str, content_type: str, expires_seconds: int | None = None
    ) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_seconds or self.default_expiry,
        )


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_mode is StorageMode.LOCAL:
        return LocalObjectStorage(settings.media_root, settings.public_media_base_url)
    return B2ObjectStorage(settings)
