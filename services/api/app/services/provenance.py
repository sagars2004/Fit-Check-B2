from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.services.object_keys import ObjectKeys
from app.services.storage import ObjectStorage


class MediaProvenanceManifest(BaseModel):
    schema_version: str = "fit-check.provenance/v1"
    run_id: str
    parent_run_id: str | None = None
    pipeline_slug: str
    tenant_id: str
    status: str = "succeeded"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    model: str
    prompt_template_version: str
    prompt_redacted: str
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    source_asset_ids: list[str] = Field(default_factory=list)
    source_object_keys: list[str] = Field(default_factory=list)
    output: dict[str, Any]
    transformations: list[dict[str, Any]] = Field(default_factory=list)
    retry_history: list[dict[str, Any]] = Field(default_factory=list)
    qa: dict[str, Any] = Field(default_factory=dict)
    manifest_hash: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"manifest_hash"})

    def canonical_hash(self) -> str:
        payload = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def finalized(self) -> MediaProvenanceManifest:
        return self.model_copy(update={"manifest_hash": self.canonical_hash()})

    def owner_view(self) -> dict[str, Any]:
        return self.finalized().model_dump(mode="json")

    def shared_view(self) -> dict[str, Any]:
        payload = self.finalized().model_dump(mode="json")
        payload.pop("tenant_id", None)
        payload.pop("source_object_keys", None)
        payload["prompt_redacted"] = "[redacted for shared link]"
        return payload


async def persist_manifest(
    storage: ObjectStorage,
    object_keys: ObjectKeys,
    manifest: MediaProvenanceManifest,
) -> tuple[str, str]:
    finalized = manifest.finalized()
    object_key = object_keys.manifest(finalized.tenant_id, finalized.run_id)
    content = json.dumps(
        finalized.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    stored = await storage.put_bytes(
        object_key,
        content,
        content_type="application/json",
        metadata={"manifest-hash": finalized.manifest_hash or ""},
    )
    return stored.key, finalized.manifest_hash or ""

