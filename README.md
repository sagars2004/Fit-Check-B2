# Fit Check

> What to wear today, from clothes you actually own.

Fit Check is a private, provenance-aware wardrobe copilot for the Backblaze
Generative AI Media Hackathon. It turns owned outfit photos into a reviewable
digital closet, recommends weather- and occasion-aware looks from approved
garments only, and creates a selected AI preview with a visible evidence trail.

## Current implementation status

Milestones 0 through 3 are complete in safe local mock mode. The repository
contains a working, credential-free path from a reviewable closet to one
selected AI preview, while keeping live GMI try-on explicitly safety-gated.
The foundation path provides:

1. Generate a deliberately generic **AI-reconstructed** mock garment cutout.
2. Validate that the PNG is RGBA, has transparent corners, and is not clipped.
3. Persist the media to local private mock storage (or configured B2 storage).
4. Persist a hash-verified, immutable provenance manifest and link it in the
   metadata database.
5. Inspect the run, object key, hashes, QA result, and provenance in the web UI.

The mock asset is explicitly not source-backed clothing evidence. Real upload,
review, evidence, and approval flows are now available as a local Milestone 1
workflow:

1. Request a server-scoped upload target. Local mock mode uses the API; B2 mode
   returns a short-lived, exact-key presigned URL without exposing credentials.
2. Validate and normalize JPG, PNG, or WebP uploads; record dimensions, a
   server-computed SHA-256, and deterministic source fingerprint.
3. Create a reviewable, immutable source crop with deliberately conservative
   attributes. The app never calls that crop a transparent cutout.
4. Edit, approve, hold for a better photo, or reject each candidate. Approval
   creates a source-backed garment plus immutable `GarmentEvidence`.
5. Run deterministic chroma removal and technical alpha QA only after a garment
   has been approved. A passing derivative remains `awaiting_review` until the
   owner approves it; a failed or rejected derivative is visibly held as
   `needs_better_photo`.
6. Compare approved cutouts conservatively using a local 16×16 luminance
   signature. A close match creates a human review record only: no automatic
   merge, archive, deletion, or ownership change is possible.
7. Browse and edit safe closet metadata without changing source evidence or
   provenance.

The local mock cutout flow is deterministic and source-derived; it does not
invoke GMI or claim generative reconstruction. Live GMI cutout generation
remains gated on the configured account capability spike and explicit model
selection.

Milestone 2 adds the **Today** planner:

1. Accept a location, date, lightweight occasion/context, and optional
   utilization preference.
2. Use keyless Open-Meteo forecast/geocoding APIs when `WEATHER_MODE=live`, or
   a deterministic offline forecast in mock mode.
3. Build and validate three diverse recommendations from approved, unarchived
   garments only. The local planner enforces top+bottom or one-piece
   completeness, cold/rain outerwear rules, no cold/rain shorts, recent-wear
   avoidance, and palette/occasion scoring.
4. Persist proposed looks, allow saving, and support reversible wear logging
   with per-garment wear counts and cost-per-wear (shown only when both price
   and a non-zero wear count exist). No image generation runs during planning.

The planner intentionally does not use a GMI LLM until the account capability
spike selects a validated structured-output model. Its deterministic rules are
the safety boundary that keeps recommendations owned-only today.

Milestone 3 adds a consent-gated **selected preview**:

1. Store a personal reference photo only after affirmative, per-upload consent;
   keep it under a separate private profile key and allow independent deletion.
2. Require the user to choose one saved recommendation and one active,
   consented profile before **Generate one AI preview** becomes available.
3. Revalidate that every selected garment is currently owned, approved,
   unarchived, and source-backed; record the exact garment and asset IDs used.
4. In mock mode, persist a deterministic, explicitly **AI-reconstructed** PNG,
   output hash, private manifest, retry lineage, and a redacted provenance view.
5. Never present the result as a sizing, fit, fabric-drape, body-shape, or
   garment-detail guarantee. A failed render remains visible and retryable;
   no substitute image is silently accepted.

Live try-on deliberately returns an actionable, durable failure until a
server-side GMI capability test proves a private runtime-only reference-image
path and a verifiable returned artifact. This prevents signed personal-image
URLs or unverified generated media from reaching a provider while preserving
the full mock demo path.

## Concise audit and build plan

The repository began as a clean baseline with only a product blurb and license;
there were no project instructions, code, dependencies, credentials, or existing
architecture to preserve. The PRD is the implementation contract.

The implementation is sequenced as follows:

1. **Foundation and provider spike** — monorepo, mock mode, schema, B2/Genblaze
   interfaces, provenance, and the account-specific GMI capability probe.
2. **Import and closet** — direct private upload, deterministic normalization and
   source-hash dedupe, review queue, evidence records, deterministic source-cutout
   QA, conservative duplicate review, and closet metadata editing.
3. **Today** — Open-Meteo context, deterministic owned-only outfit constraints,
   three diverse recommendations, saved looks, and reversible wear logging.
4. **Selected preview and provenance** — complete in mock mode: consented
   reference photos, one selected-look preview, retries/fallback, and a
   redacted provenance explorer. Live VTON remains gated on the provider spike.
5. **Polish and submission** — next: demo data, accessibility, failure/empty
   states, deployment checklist, and the three-minute judge flow.

## Architecture

```mermaid
flowchart LR
  Browser["Next.js web"] --> API["FastAPI API"]
  API --> DB["PostgreSQL metadata"]
  API --> Store["B2 private objects\n(or local mock storage)"]
  API --> Workflows["Durable workflows"]
  Workflows --> Genblaze["Genblaze pipeline + manifest"]
  Genblaze --> GMI["GMI Cloud"]
  Workflows --> QA["Local deterministic\nnormalization / QA / hashes"]
  QA --> Store
```

- The browser receives no B2 or GMI credentials.
- PostgreSQL stores relational state; B2 stores originals, derivatives, generated
  assets, and manifests.
- GMI model IDs are configurable and intentionally blank until the configured
  account capability probe has passed.
- Genblaze is the live provider orchestration boundary, using its B2
  `ObjectStorageSink` and hash-verified manifests. Fit Check adds bounded
  retry-ledger handling around retryable failed runs. Mock mode supplies a
  deterministic offline analogue so contributors can develop without credits.

## Local development

Prerequisites: Node 20+, npm 10+, Docker (optional for PostgreSQL), and
[uv](https://docs.astral.sh/uv/) with Python 3.11+ available.

```bash
cp .env.example .env
make install
make dev-api
```

In another terminal:

```bash
make dev-web
```

Open [http://localhost:3000](http://localhost:3000). With the default mock
configuration, click **Run mock provenance pipeline**. The API starts at
[http://localhost:8000](http://localhost:8000), with its health endpoint at
[http://localhost:8000/health](http://localhost:8000/health).

Mock mode uses SQLite and `local-media/` by default. Both are ignored by Git.
For a local PostgreSQL instance:

```bash
make db-up
# Set DATABASE_URL=postgresql+asyncpg://fitcheck:fitcheck@localhost:5432/fitcheck in .env
make migrate
```

Useful checks:

```bash
make test
make lint
make typecheck
make build
```

The initial import UI accepts JPG, PNG, and WebP files up to the configured
`MAX_UPLOAD_BYTES` value (15 MB by default). Each successful local upload is
normalized and ready for review before an import job is created. Failed files
remain isolated from other selected photos.

To exercise the selected-preview path in mock mode, approve enough wardrobe
items to receive a recommendation, click **Preview on me** on exactly one look,
then upload a JPG/PNG/WebP reference photo and affirm the consent checkbox.
The saved reference photo can be removed independently. The local preview is a
deterministic demo visualization, clearly labeled as AI-reconstructed.

The Today UI defaults to a deterministic offline weather snapshot. Set
`WEATHER_MODE=live` to enable the server-side, keyless Open-Meteo lookup; if a
live lookup fails, Fit Check labels and falls back to the deterministic forecast
instead of silently presenting it as live weather.

## Environment configuration

Copy [`.env.example`](.env.example). It documents every runtime variable,
including B2, GMI, local mock storage, quotas, CORS, and optional fallback
configuration. Do not commit `.env` or any credentials.

### B2 activation

Use a private bucket and a least-privilege application key. Set:

```dotenv
STORAGE_MODE=b2
B2_BUCKET=...
B2_KEY_ID=...
B2_APP_KEY=...
B2_ENDPOINT_URL=...
B2_REGION=...
```

You may keep `PROVIDER_MODE=mock` while validating B2 persistence without using
any GMI credits. In this mode, `POST /v1/uploads/presign` returns a scoped B2
upload URL; the server then reads, hashes, validates, and normalizes the object
before it can enter an import job. Object keys follow the PRD layout under
`fit-check/users/{user_id}/...`, including uploads, crops, masks, cutouts,
looks, manifests, exports, and separate private
`profiles/{profile_id}/reference.*` objects.

### GMI and Genblaze activation

Do not turn this on until server-side credentials and a private B2 bucket are
available. No GMI model name is hard-coded in Fit Check.

```dotenv
PROVIDER_MODE=live
STORAGE_MODE=b2
GMI_API_KEY=...
GMI_ORG_ID=...
ENABLE_PROVIDER_SMOKE_TESTS=true
# Set only after reviewing the configured account's capability probe:
GMI_VISION_MODEL=
GMI_IMAGE_MODEL=
GMI_TRYON_MODEL=
```

Then run:

```bash
make gmi-smoke
```

The deliberate, server-only probe lists available GMI media and LLM models; it
does not choose one or expose keys. Before enabling live garment or try-on
generation, record a tested vision JSON model, reference-image model, latency,
cost, output shape, and retry behavior in `docs/provider-spike.md`.

`GMI_TRYON_MODEL` alone does not enable live personal-image previewing. The M3
workflow remains blocked until the capability record confirms that personal
reference media is supplied privately at runtime (not retained in a provider
manifest), source media URLs are not persisted, and the provider output can be
retrieved and hash-verified before it is marked ready.

## Data and provenance

The initial schema covers the PRD entities: users, reference profiles, uploads,
import jobs, candidates, garments, evidence, garment assets, duplicate reviews,
outfits/items, try-on renders, wear events, and provenance links. The migration
is at [0001_milestone_zero.py](services/api/app/db/migrations/versions/0001_milestone_zero.py).

Every generated asset records its input/output SHA-256, provider/model, redacted
prompt template, parameters, QA result, run and parent-run IDs, object key, and
manifest hash. Imported candidates preserve their original upload/source crop
and carry one of three visible evidence states: `verified_source_backed`,
`ai_reconstructed`, or `needs_better_photo`. Selected preview manifests add the
profile and exact garment-source asset IDs without retaining signed URLs or raw
correction text. The current provenance endpoint returns a private, redacted
record and never persists signed URLs.

## Attribution

Fit Check borrows product patterns—not implementation or media—from the
MIT-licensed [tandpfun/wardrobe](https://github.com/tandpfun/wardrobe) and
Backblaze Labs'
[Genblaze multi-provider sample](https://github.com/backblaze-labs/genblaze-gen-media-multi-provider-sample).
See [NOTICE.md](NOTICE.md). No source code from either project has been copied
into this repository.
