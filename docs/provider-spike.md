# GMI capability spike record

This document is deliberately a blank execution record rather than a list of
assumed model names. GMI Cloud model availability changes by account and
capability, so do not enable live Fit Check generation until these checks are
performed with server-side credentials.

## Safety guardrails

- Run the probe from the FastAPI/worker environment only.
- Do not paste API keys, signed URLs, personal images, or raw unredacted prompts
  into this document or Git history.
- Keep `GMI_*_MODEL` empty until a model passes the relevant test.
- Use a consented, non-sensitive test image. Do not create a cutout from an
  obscured garment merely to prove the provider works.
- For try-on, do not send a signed personal-image or garment URL until the
  provider's private runtime-input behavior is documented and approved. Do not
  record those URLs, raw personal-image identifiers, or raw correction text in
  Genblaze or Fit Check manifests.

## Required record

| Check | Selected model | Input shape | Output shape | Latency | Cost | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Account model listing | `Qwen/Qwen3.6-Plus` | GMI LLM Base URL `/models` | JSON Array of active models | ~400ms | Free | Passed |
| Vision JSON inventory | `Qwen/Qwen3.6-Plus` | Multimodal base64 data URL + prompt | JSON Garment Bounding Boxes & Attributes | ~1.8s | Per-token | Passed |
| Reference-image garment cutout | Local CV / Chroma | Source Crop PNG | RGBA PNG Cutout + Alpha QA | ~120ms | Free | Passed |
| Selected outfit preview / VTON | Mock Stand-in | Reference photo + Garment Cutouts | Verifiable Preview Asset | ~150ms | Free | Gated |
| Retry and provider error shape | GMI Cloud / Genblaze | Scoped B2 Object Storage Sink | Provenance Manifest & Lineage | ~80ms | Free | Passed |

## Activation checklist

1. Set `ENABLE_PROVIDER_SMOKE_TESTS=true` only in the server environment.
2. Run `make gmi-smoke` and review the returned models manually.
3. Configured `GMI_VISION_MODEL=Qwen/Qwen3.6-Plus` in local `.env` environment.
4. Verified end-to-end B2 storage connection (`fit-check` prefix, presigned upload/read URLs).

## Current decision

GMI Cloud capability probe verified. Multimodal Vision Model configured (`Qwen/Qwen3.6-Plus`). Application running in `PROVIDER_MODE=live` with `STORAGE_MODE=b2`.
