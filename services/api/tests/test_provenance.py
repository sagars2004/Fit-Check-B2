import json

from app.services.provenance import MediaProvenanceManifest


def test_manifest_hash_is_stable_and_shared_view_redacts() -> None:
    manifest = MediaProvenanceManifest(
        run_id="run-1",
        pipeline_slug="fit-check-m0-cutout",
        tenant_id="demo-user",
        provider="mock",
        model="mock-v1",
        prompt_template_version="v1",
        prompt_redacted="[redacted]",
        source_object_keys=["fit-check/users/demo-user/uploads/private.jpg"],
        output={"object_key": "fit-check/users/demo-user/garments/a/cutouts/1.png"},
    )

    finalized = manifest.finalized()
    assert finalized.manifest_hash == manifest.canonical_hash()
    assert finalized.finalized().manifest_hash == finalized.manifest_hash
    assert "tenant_id" not in finalized.shared_view()
    assert "source_object_keys" not in finalized.shared_view()
    assert (
        json.loads(json.dumps(finalized.owner_view()))["manifest_hash"] == finalized.manifest_hash
    )
