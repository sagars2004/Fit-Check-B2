# Fit Check local mock demo runbook

This is the operator guide for the current Fit Check MVP, including its
Milestone 4 demo polish. It supports a repeatable **local, credential-free**
walkthrough. It is not a claim that Fit Check is deployed or that a live B2,
Genblaze, or GMI run has been completed.

## What this demo proves

- A reviewable closet can contain only approved, source-backed owned garments.
- The planner produces three weather- and occasion-aware, owned-only looks
  without automatically generating images.
- A user explicitly selects one look and a consented reference profile before
  requesting one AI preview.
- Mock media, manifests, hashes, source IDs, retry lineage, and redacted
  provenance are stored durably in the configured local mock storage.
- The UI clearly distinguishes verified source evidence, AI-reconstructed
  media, and items that need a better photo. It also states that a preview is
  not a fit, sizing, fabric-drape, body-shape, or garment-detail guarantee.

## What this demo does not claim

- No deployed judge URL exists yet.
- Default mock mode does not contact Backblaze B2, Genblaze, GMI Cloud, or
  Open-Meteo, and it does not spend provider credits.
- No GMI model has been selected or invoked. `GMI_TRYON_MODEL` is intentionally
  insufficient to enable live personal-image previewing.
- The local selected-preview image is a deterministic AI-reconstructed demo
  visualization, not virtual try-on evidence or a real fit simulation.

## Preflight

Use a fresh terminal in the repository root. Keep the default values in
`.env`: `PROVIDER_MODE=mock`, `STORAGE_MODE=local`, and `WEATHER_MODE=mock`.
Do not place credentials in `.env` for this walkthrough.

```bash
cp .env.example .env
make install
make migrate
make dev-api
```

In a second terminal:

```bash
make dev-web
```

Open [http://localhost:3000](http://localhost:3000). The API health response
is available at [http://localhost:8000/health](http://localhost:8000/health).

Before recording or presenting, run the checks appropriate to the available
time:

```bash
make test
make lint
make typecheck
make build
```

The app uses a local SQLite database and `local-media/` in mock mode. Both are
ignored by Git. Use a clean local database/media root for a clean demo; do not
delete a shared or production data directory as a presentation shortcut.

## Prepare a repeatable demo wardrobe

Use the local mock demo seed exposed by the **Load safe demo wardrobe** action
in the Closet section, or call its local-only API endpoint:

```bash
curl -X POST http://localhost:8000/v1/demo/seed
```

The seed is intentionally local/mock-only and idempotent: it creates synthetic
non-personal source evidence, approved owned garments, and a held item. It
deliberately does **not** create a personal reference profile. It must never be
used to represent real wardrobe data. Re-running it should preserve the
existing local demo state rather than overwrite it.

To demonstrate the selected-preview flow, add a consented, non-sensitive test
reference photo through the UI and affirm the consent checkbox. The stored
profile is separate from the seeded wardrobe and can be deleted independently.

If showing the real import/review path instead, use only consented test photos.
Upload JPG, PNG, or WebP files, review each preserved source crop, and approve
only items whose visible source evidence supports the item. Hold poor or
occluded photos rather than presenting a fabricated cutout.

## Three-minute walkthrough

Keep the mock-mode disclosure visible in the narration. The goal is to show the
user value and the durable evidence trail without implying a live provider run.

| Time | Screen and action | Narration / proof point |
| --- | --- | --- |
| 0:00–0:20 | Landing page | “Fit Check answers what to wear today from clothes you actually own. Trust comes from human review and provenance, not from invented fashion.” |
| 0:20–0:50 | Import and closet | Show a source crop, an approved garment, and—if useful—a held item. Explain that approval preserves source evidence and that close duplicate matches are review prompts, never automatic merges. |
| 0:50–1:20 | Today | Use the default local weather snapshot and an occasion such as “Rainy workday.” Click **Plan three looks** and point out the owned-only badge, weather explanation, and diverse approved-item cards. |
| 1:20–1:45 | Today / selected look | Click **Preview on me** on exactly one recommendation. Explain that planning itself creates no image and that selection is required before a preview can be requested. |
| 1:45–2:15 | Selected AI preview | Add or choose a consented non-sensitive reference profile, then click **Generate one AI preview**. Call out the AI-visualization disclosure, exact source garment cards, and retry behavior. Do not call the image a fit prediction. |
| 2:15–2:40 | Preview provenance | Open **How this was made**. Show the local/mock provider label, output hash, object key, exact source IDs, run/parent-run lineage, and redacted manifest. State that signed URLs and raw correction text are not retained in the record. |
| 2:40–3:00 | Today / close | Optionally save or log a wear, then summarize: local deterministic processing lowers cost; a B2/Genblaze/GMI live path is configured but intentionally gated pending an approved capability test. |

## Useful recovery paths during a demo

| Situation | Safe response |
| --- | --- |
| No wardrobe items | Run the local mock seed and refresh the page. The seed is intentionally non-personal and does not overwrite existing items. |
| No available profile | Use an authorized, non-sensitive test photo and affirm the per-upload consent checkbox. The seed deliberately never creates a personal reference profile. |
| The planner says the wardrobe lacks coverage | Use the seeded wardrobe or add and approve the needed source-backed category. Held, archived, and unreviewed candidates are correctly excluded. |
| A preview fails | Keep the selected look; use the visible retry action after reading the stable error. The retry records parent-run lineage and does not silently substitute a different look. |
| A cutout is rejected by QA | Show the `needs_better_photo` state. This is the intended fidelity-preserving behavior; do not relabel it as a verified cutout. |
| Someone asks whether the preview is real VTON | Say: “This local demo is a deterministic AI preview. We will only enable GMI-backed personal-image generation after the private-input and verifiable-output capability record is approved.” |

## Optional live validation — not part of this runbook

Only the project owner may authorize a live validation. Before any such work,
complete every pending item in [provider-spike.md](provider-spike.md), use a
separate private B2 environment, and verify all of the following:

1. The configured GMI account accepts private reference media at runtime
   without retaining signed URLs in a manifest.
2. The provider returns retrievable output bytes or a controlled B2 artifact
   whose SHA-256 can be verified before the preview is marked ready.
3. Genblaze receives the tenant ID, bounded retry policy, parent-run lineage,
   and B2 sink configuration for the actual selected-preview pipeline.
4. No secret, signed URL, personal reference image, or raw correction text is
   exposed to the browser, logs, or Git history.

Until those conditions are documented and explicitly approved, present the
mock walkthrough only.
