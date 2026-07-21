# Fit Check

> What to wear today, from clothes you actually own.

Fit Check is a private, provenance-aware wardrobe copilot for the Backblaze
Generative AI Media Hackathon. It turns owned outfit photos into a reviewable
digital closet, recommends weather- and occasion-aware looks from approved
garments only, and creates a selected AI preview with a visible evidence trail.

## Current implementation status

Milestone 0 is complete. This repository now contains a working, credential-free
proof of the most important infrastructure path:

1. Generate a deliberately generic **AI-reconstructed** mock garment cutout.
2. Validate that the PNG is RGBA, has transparent corners, and is not clipped.
3. Persist the media to local private mock storage (or configured B2 storage).
4. Persist a hash-verified, immutable provenance manifest and link it in the
   metadata database.
5. Inspect the run, object key, hashes, QA result, and provenance in the web UI.

The mock asset is explicitly not source-backed clothing evidence. Real upload,
review, evidence, and approval flows are Milestone 1 work.

## Concise audit and build plan

The repository began as a clean baseline with only a product blurb and license;
there were no project instructions, code, dependencies, credentials, or existing
architecture to preserve. The PRD is the implementation contract.

The implementation is sequenced as follows:

1. **Foundation and provider spike** — monorepo, mock mode, schema, B2/Genblaze
   interfaces, provenance, and the account-specific GMI capability probe.
2. **Import and closet** — direct private upload, deterministic normalization and
   dedupe, review queue, evidence records, cutout generation, QA, and closet
   metadata editing.
3. **Today** — Open-Meteo context, deterministic owned-only outfit constraints,
   three diverse recommendations, saved looks, and wear/ROI logging.
4. **Selected preview and provenance** — consented reference photos, one
   selected-look preview, retries/fallback, and the full provenance explorer.
5. **Polish and submission** — failure/empty states, demo data, accessibility,
   deployment checklist, and the three-minute judge flow.

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
any GMI credits. Object keys follow the PRD layout under
`fit-check/users/{user_id}/...`, including uploads, crops, masks, cutouts,
looks, manifests, and exports.

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

## Data and provenance

The initial schema covers the PRD entities: users, reference profiles, uploads,
import jobs, candidates, garments, evidence, garment assets, duplicate reviews,
outfits/items, try-on renders, wear events, and provenance links. The migration
is at [0001_milestone_zero.py](services/api/app/db/migrations/versions/0001_milestone_zero.py).

Every generated asset records its input/output SHA-256, provider/model, redacted
prompt template, parameters, QA result, run and parent-run IDs, object key, and
manifest hash. The current provenance endpoint never persists signed URLs.

## Attribution

Fit Check borrows product patterns—not implementation or media—from the
MIT-licensed [tandpfun/wardrobe](https://github.com/tandpfun/wardrobe) and
Backblaze Labs'
[Genblaze multi-provider sample](https://github.com/backblaze-labs/genblaze-gen-media-multi-provider-sample).
See [NOTICE.md](NOTICE.md). No source code from either project has been copied
into this repository.
