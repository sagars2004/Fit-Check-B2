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
| Account model listing |  |  |  |  |  | Pending |
| Vision JSON inventory |  |  |  |  |  | Pending |
| Reference-image garment cutout |  |  |  |  |  | Pending |
| Selected outfit preview / VTON or edit |  | Private runtime-only reference + owned asset inputs | Verifiable image bytes/key + hash |  |  | Pending |
| Retry and provider error shape |  |  |  |  |  | Pending |

## Activation checklist

1. Set `ENABLE_PROVIDER_SMOKE_TESTS=true` only in the server environment.
2. Run `make gmi-smoke` and review the returned models manually.
3. Call each selected model with a tiny consented test payload; capture the
   accepted private reference-input mechanism, expected output artifact
   behavior, and error body. Do not commit personal-image URLs or credentials.
4. Verify that the image model supports the required source evidence input. If it
   does not, retain the garment as `needs_better_photo`; never silently invent
   invisible construction details.
5. Set `GMI_VISION_MODEL`, `GMI_IMAGE_MODEL`, and/or `GMI_TRYON_MODEL` in the
   server secret store only after the test passes.
6. Run an end-to-end B2 + Genblaze test. Verify that private input URLs are
   runtime-only (not in a persisted manifest), the B2 output exists, and its
   SHA-256 agrees with the Genblaze and Fit Check manifest records.
7. Record an approved provider/model/fallback choice and cost controls here.

## Current decision

No GMI model has been selected or invoked from this repository. The application
therefore defaults to `PROVIDER_MODE=mock` and cannot accidentally spend credits.
