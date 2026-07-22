# Fit Check: current implementation and real-data launch roadmap

This document is the implementation handoff for moving Fit Check from its
safe, credential-free local MVP to a real-data application backed by Backblaze
B2, Genblaze, and GMI Cloud. It is grounded in the separately supplied
`Fit-Check-PRD.md` and the code currently in this repository; the PRD remains
the product source of truth.

It deliberately distinguishes four states:

| Status | Meaning |
| --- | --- |
| **Implemented locally** | Runs and is tested in local mock mode. |
| **Integration boundary exists** | Interfaces and configuration exist, but no real account has validated the path. |
| **Safety-gated** | The application intentionally refuses the action until a privacy/capability condition is proven. |
| **Not yet implemented** | Product or production capability still needs design and code. |

## Executive summary

Fit Check already has a strong end-to-end product shell: reviewable wardrobe
records, evidence-aware garments, deterministic cutout QA, owned-only weather
recommendations, consented selected-preview UX, private-object abstractions,
provenance records, and a polished local demo path.

It is **not** yet a real generative-media deployment. No B2 or GMI credentials
have been used; no GMI model has been selected; no Genblaze pipeline has run
against a real account; and no public deployment exists. Supplying model IDs by
itself will not turn on real try-on. The live preview route is deliberately
blocked until its private reference-input and verifiable-output behavior have
been tested.

The critical remaining work is therefore not UI polish. It is: secure
infrastructure, account-specific model validation, real vision/cutout/try-on
pipeline work, durable async execution, tenant isolation, and a staging-to-
judge deployment rehearsal.

## What is already implemented

### 1. Foundation, configuration, metadata, and object storage

**Implemented locally / integration boundary exists**

- Next.js/TypeScript web app and FastAPI/Python API in one repository.
- SQLAlchemy metadata models for users, profiles, uploads, import jobs,
  candidates, garments, source evidence, assets, duplicate reviews, outfits,
  renders, wear events, and provenance links.
- SQLite local development by default, Alembic migration support, and a
  PostgreSQL-compatible async database configuration.
- Private object-key conventions for raw uploads, normalized files, source
  crops, masks, cutouts, look renders, manifests, and profile reference images.
- Local object storage for a zero-credential demo plus a Backblaze B2
  S3-compatible storage adapter with scoped presigned read/upload URLs,
  server-side SHA-256 checks, and private-object metadata.
- Complete `.env.example` with server-only B2/GMI settings; no browser-exposed
  provider credentials.
- Hash-addressed Fit Check provenance manifests with run ID, parent run ID,
  provider/model, redacted prompt policy, parameters, source IDs/object keys,
  output hash, QA, and retry history.

Relevant code: [storage adapter](../services/api/app/services/storage.py),
[object keys](../services/api/app/services/object_keys.py),
[configuration](../services/api/app/core/config.py), and
[provenance service](../services/api/app/services/provenance.py).

**Not yet verified against a real account**

- A real B2 bucket, CORS policy, lifecycle policy, least-privilege application
  key, and actual upload/read/delete behavior.
- A deployed PostgreSQL database and environment-specific migration process.

### 2. Import, review, closet, and deterministic QA

**Implemented locally**

- JPG, PNG, and WebP private uploads with normalization, dimensions,
  SHA-256, duplicate handling, immutable source crops, and review states.
- Human candidate review: edit, approve, hold for a better photo, or reject.
- Approved garments preserve immutable `GarmentEvidence` records.
- Deterministic chroma removal and alpha QA create reviewable cutouts; only an
  approved output becomes the canonical cutout.
- Conservative local duplicate ranking produces a review record only; it never
  merges or deletes garments automatically.
- Closet display, text filtering, metadata edits, archiving, evidence labels,
  cutout review, and duplicate review UI.

Relevant code: [import/closet workflow](../services/api/app/workflows/milestone_one.py)
and [closet UI](../apps/web/components/wardrobe-import.tsx).

**Current real-data limitation**

The importer currently creates one conservative, generic candidate from each
uploaded image and uses deterministic local cropping/attributes. It does not
yet use GMI vision to find multiple garments in an outfit photo, infer robust
structured attributes, or return model-backed bounding boxes. The current
cutout path is deterministic chroma removal, not a real GMI reconstruction or
image-edit pipeline; ordinary real-world outfit photos will therefore often be
correctly held rather than becoming usable transparent catalog assets.

### 3. Weather-aware recommendations and wear tracking

**Implemented locally**

- Deterministic rule-first planner that uses approved, unarchived, owned
  garments only.
- Weather/occasion context, palette checks, cold/rain constraints, recent-wear
  avoidance, utilization preference, three diverse options, save, wear, undo,
  wear count, and cost-per-wear behavior.
- Keyless Open-Meteo integration is available when `WEATHER_MODE=live`; mock
  weather remains the local default.

Relevant code: [planner workflow](../services/api/app/workflows/milestone_two.py)
and [Today UI](../apps/web/components/today-planner.tsx).

**Still useful to add**

- Real saved-look browsing/lookbook and garment insights (most worn, least
  worn, recently worn).
- Richer wardrobe filtering by category, color, season, status, and wear
  count; the current UI has text filtering.
- Optional structured LLM explanation/diversification only after a model has
  passed the capability spike. The deterministic owned-only constraints should
  remain the hard safety boundary.

### 4. Selected preview, consent, lineage, and provenance

**Implemented locally**

- Per-upload affirmative consent before a reference image is stored.
- Separate private profile object keys and independent reference-photo deletion.
- One selected-look preview request only after a user picks an outfit and an
  active consented profile.
- Server-side revalidation that every garment remains approved, owned,
  unarchived, and source-backed.
- Exact selected garment IDs/source asset IDs, output hash, source cards,
  progress/retry states, AI-visualization disclosure, durable failed-render
  records, and parent-run lineage.
- A redacted "How this was made" drawer that omits signed URLs, raw prompt
  text, tokens, and credentials.

Relevant code: [preview workflow](../services/api/app/workflows/milestone_three.py),
[preview UI](../apps/web/components/try-on-studio.tsx), and
[provider contract](../services/api/app/providers/contracts.py).

**Safety gate that remains intentional**

The mock preview is a deterministic, clearly AI-reconstructed visualization.
In live mode, the preview workflow first requires `GMI_TRYON_MODEL`, then
returns `TRYON_LIVE_INPUTS_UNVERIFIED` **before any signed personal-image URL
can reach a provider**. This must remain true until the provider capability
test proves a private, runtime-only reference-image mechanism and a verifiable
output artifact.

### 5. M4 demo polish and documentation

**Implemented locally**

- Keyboard/focus improvements, skip navigation, responsive/mobile styling,
  empty states, reload/retry affordances, and an explicit Closet → Today →
  Preview judge journey.
- An additive local-only synthetic fixture is available for development. It is
  visibly disclosed, idempotent, never creates a reference profile, and is
  disabled outside local mock mode.
- A local demo runbook and an honest submission checklist explain what can and
  cannot be claimed today.

Relevant documents: [demo runbook](demo-runbook.md),
[submission checklist](submission-checklist.md), and [provider spike record](provider-spike.md).

The synthetic seed is a developer/demo fallback only. It should not be the
primary dataset for a real generative-media demonstration once consented real
assets are available.

## What must be completed for a real, non-mock app

### A. Establish real infrastructure and secrets

Create separate development/staging/demo resources before enabling live mode:

1. A **private Backblaze B2 bucket** or dedicated demo prefix.
2. A least-privilege B2 application key that can access only the intended
   bucket/prefix.
3. B2 CORS rules for the deployed web origin and scoped browser uploads.
4. B2 lifecycle/retention rules for temporary uploads, rejected derivatives,
   and user-deletion handling.
5. A managed PostgreSQL database for staging/demo metadata.
6. A secret store or server-only deployment environment for B2/GMI keys.
7. Separate API/worker and web deployment targets.

The live environment needs values such as these, set only in a server-side
secret store or local untracked `.env` file:

```dotenv
APP_ENV=staging
PROVIDER_MODE=live
STORAGE_MODE=b2
DATABASE_URL=postgresql+asyncpg://...
WEB_ORIGIN=https://your-web-origin.example

B2_ENDPOINT_URL=...
B2_REGION=...
B2_BUCKET=...
B2_KEY_ID=...
B2_APP_KEY=...
B2_PREFIX=fit-check-demo

GMI_API_KEY=...
GMI_ORG_ID=...
ENABLE_PROVIDER_SMOKE_TESTS=true
GMI_VISION_MODEL=
GMI_IMAGE_MODEL=
GMI_TRYON_MODEL=
```

Do not paste secret values into chat, commit them, or put them in
`NEXT_PUBLIC_*` variables. Keep model IDs blank until the capability tests
below have selected them.

### B. Complete the account-specific GMI capability spike

This is the first authorized action after infrastructure is ready. It is not
optional because model IDs and multimodal input contracts vary by account.

1. Authorize a server-side model listing (`make gmi-smoke`).
2. Record candidate media and LLM models in [provider-spike.md](provider-spike.md).
3. With a tiny consented, non-sensitive test set, validate separately:
   - structured vision/inventory output;
   - one or more reference-image cutout or edit behavior;
   - selected-look/VTON or image-edit behavior with a personal reference image
     and exact garment inputs;
   - accepted private input mechanism;
   - output response shape, retrievable bytes or controlled B2 artifact,
     latency, cost, retryable errors, and provider correlation IDs.
4. Verify that personal reference URLs are runtime-only and do not appear in
   provider or Fit Check manifests.
5. Set only the tested model IDs in the secret store and update the spike
   record with the evidence.

### C. Finish the real Genblaze/GMI adapter before enabling generation

The current [`GenblazeGMICloudOrchestrator`](../services/api/app/providers/gmi.py)
is an architectural scaffold, not a completed live media path. In particular:

- It needs the capability-tested provider parameter mapping rather than an
  assumed `reference_image_urls` field.
- It should pass the Fit Check tenant/user ID into the Genblaze pipeline.
- It should configure the B2 sink prefix deliberately instead of accepting the
  SDK default.
- It currently returns `GeneratedMedia(content=None)` and an asset URL. The
  preview workflow correctly rejects that as unverifiable. Implement one
  approved output strategy: retrieve image bytes server-side and validate them,
  or verify a controlled Genblaze/B2 artifact by exact key, size, and SHA-256
  before marking a render ready.
- It needs to preserve Genblaze run/step/manifest identifiers in the Fit Check
  provenance record without storing signed input URLs or raw prompts.
- It needs a bounded, capability-tested fallback chain only when source
  fidelity is preserved; fallback must never silently substitute a lower
  fidelity result.

### D. Build the real media workflows

#### Real import and inventory

- Replace one-candidate local extraction with a vision-backed pipeline that can
  identify one or more garments, source bounding boxes, category, colors,
  material/pattern hypotheses, confidence, and unresolved details.
- Keep local normalization, hashing, duplicate ranking, and source evidence as
  deterministic guardrails.
- Retain human approval before a candidate becomes owned inventory.
- Add individual failed-candidate retry and preserve partial batch success.

#### Real cutouts

- Use the tested GMI image/edit model only after source evidence passes a
  minimum-quality gate.
- Supply source-specific constraints that exclude the wearer, skin, hair,
  adjacent garments, props, hangers, and invented details.
- Run deterministic alpha/chroma/padding checks after generation.
- Add visual QA and a correction/retry loop; hold an item when it cannot be
  validated rather than presenting a reconstructed asset as verified.

#### Real selected previews

- Enable the live M3 path only after the privacy/output checks pass.
- Use exactly one selected outfit plus a selected consented profile.
- Send only private, short-lived, capability-approved inputs at runtime.
- Validate output bytes, persist the ready preview in B2, and make its
  provenance traceable to exact garment asset IDs, user profile, Genblaze run,
  parent run, model, and output hash.
- Support an actionable retry and an explicitly configured fallback/defer
  outcome. Do not claim size, fit, drape, body shape, or garment-detail
  accuracy.

### E. Replace the fixed demo-user model with real authorization

Every current workflow resolves the fixed `DEMO_USER_ID`. That is suitable for
local development only. Before personal data is exposed to a judge or user,
implement:

- authentication (a controlled single demo account is acceptable for the
  hackathon; passwordless or a managed identity provider is better for a
  multi-user app);
- a request-scoped authenticated user ID on every API query, upload target,
  render, provenance lookup, and B2 key;
- owner checks for every read/write/delete action;
- admin-only server-side provider capability operations;
- owner-authorized scoped download/share URLs;
- no predictable cross-user media access.

### F. Make media jobs durable and observable

Current imports and preview generation are synchronous request workflows.
Real provider work needs to outlive an API request/restart.

- Introduce a database-backed job/run state machine and worker process.
- Queue import, cutout, and preview work; retain stage/error/retry state.
- Poll or stream job events to the UI (SSE is the PRD’s suggested first
  implementation).
- Enforce daily generation quotas and per-user/global concurrency limits;
  configuration exists today but enforcement does not.
- Add request IDs, user-safe structured logs, run IDs, provider/model,
  latency, error class, retry count, and provider cost when available.
- Add retry/cancel/defer paths that preserve the selected outfit and evidence.

### G. Complete privacy, deletion, and product gaps

Before calling the app fully fleshed out, add:

- garment deletion, account/data deletion, export, and documented B2 derivative
  and manifest cleanup/retention behavior;
- full closet filters and edits for colors, seasons, purchase date, notes,
  status, and wear count;
- saved-look browsing, wardrobe ROI/insights, and recently/least/most worn
  views;
- HEIC conversion support where the deployment environment permits it;
- authorized preview download/share behavior;
- browser E2E, accessibility, mobile, and failure-state testing.

## Recommended delivery sequence

| Phase | Goal | Requires credentials? | Exit condition |
| --- | --- | ---: | --- |
| 0. Scope and data | Choose a single-demo-account or multi-user auth model; prepare 10–20 consented garment/reference images and a privacy notice. | No | A controlled real dataset and demo policy exist. |
| 1. Infrastructure | Provision B2, PostgreSQL, secret management, CORS, retention, staging API/web/worker. | Yes | Private B2 upload/read/delete and database migration pass in staging. |
| 2. Capability spike | List and test account-specific GMI models with tiny non-sensitive inputs. | Yes | `provider-spike.md` records tested models and safe I/O contracts. |
| 3. Live adapter | Implement capability-specific Genblaze/GMI output handling, tenant lineage, hash verification, retries, and fallback policy. | Yes | One controlled B2 + Genblaze + GMI artifact is verified end-to-end. |
| 4. Real import/cutout | Add actual vision extraction and GMI-backed cutout path with human review/QA. | Yes | A consented real garment photo becomes a reviewed, B2-backed catalog asset. |
| 5. Real preview | Enable tested selected-look preview path. | Yes | One consented reference + approved outfit produces a verifiable B2 preview and provenance manifest. |
| 6. Production hardening | Auth, jobs/progress, quotas, deletion, logging, E2E tests, deployment rehearsal. | Yes | A non-developer judge can complete the happy path without developer credentials. |

## Suggested real demo dataset

For the fastest credible hackathon flow, use a controlled, consented wardrobe
of roughly 10–20 garments rather than relying on arbitrary camera-roll photos.
Prefer individual garment shots, flat lays, mannequins, or clean-background
photos for the first live cutout test. Include:

- several tops, bottoms, outerwear, and footwear so the planner can return
  three materially different looks;
- one intentionally poor/occluded image to demonstrate `needs_better_photo`;
- one consented, non-sensitive reference image used only for the selected
  preview test;
- a documented owner/consent record for every image.

This approach demonstrates real ownership, review, B2 persistence, Genblaze
lineage, GMI generation, and responsible failure handling without pretending
that a generic model can flawlessly catalog an uncontrolled photo archive.

## PRD completion gate

The project should only claim the full hackathon definition of done after all
of the following are true:

- a judge-accessible deployed URL exists;
- real consented photos are imported into a reviewable wardrobe;
- B2 contains raw inputs, derivatives, generated assets, and manifests;
- Genblaze has orchestrated at least one real import/cutout or preview run;
- a tested GMI model has produced at least one real media result;
- recommendations remain approved-owned-only;
- one real preview traces back to exact source garments and its B2/Genblaze
  provenance;
- secrets are absent from Git/client code and a non-developer judge can use the
  flow;
- the three-minute demo is rehearsed against the deployed app.

## Immediate next action

When the B2, database, and GMI credentials have been configured in a private
environment, explicitly authorize the **server-side GMI capability smoke test**.
Do not send the secrets through chat. The smoke test and a small controlled
input test should be the next implementation increment; only after their
recorded results should model IDs be selected and live generation code enabled.
