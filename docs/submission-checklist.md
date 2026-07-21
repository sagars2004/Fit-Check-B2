# Fit Check submission checklist

Use this checklist to prepare an accurate Backblaze Generative AI Media
Hackathon submission. It reflects the supplied PRD and the current repository;
it intentionally separates local implementation from unverified live claims.

## Current status at a glance

| PRD outcome | Current status | Evidence / limitation |
| --- | --- | --- |
| Reviewable private wardrobe | Local mock path implemented | Upload, source crop, review, conservative duplicate review, closet editing, and cutout QA are available locally. |
| Owned-only, weather-aware recommendations | Local mock path implemented | The deterministic planner returns three approved-item looks; mock weather is the default. |
| One selected preview with provenance | Local mock path implemented | Consent-gated profile handling, exact source garment IDs, retry lineage, hash/object-key record, and redacted provenance are available locally. |
| Backblaze B2 persistence | Integration-ready, unverified | B2 configuration and scoped-upload/storage interfaces exist; no B2 credentials or live persistence were used. |
| Genblaze orchestration | Integration boundary present, unverified live | The mock path preserves analogous manifests and lineage. A live selected-preview pipeline has not been authorized or run. |
| GMI Cloud generation | Pending capability spike | No model is hard-coded, selected, or invoked. Live personal-image preview is safety-gated. |
| Judge-accessible deployment | Pending | No deployment, public URL, or public demo account exists. |

Do not mark the project “submission-ready” on the basis of the local mock
walkthrough alone. The PRD definition of done requires a deployed URL and at
least one real B2-, Genblaze-, and GMI-backed generation path.

## Local implementation evidence

- [x] No OpenAI API key, GPT Image, or Codex runtime dependency is configured.
- [x] `.env.example` documents server-only GMI/B2 settings and defaults to
  credential-free mock mode.
- [x] Raw uploads, source crops, cutouts, look previews, manifests, hashes,
  lineage, and metadata have defined private storage/key boundaries.
- [x] Recommendations validate approved owned garments only and do not create
  previews automatically.
- [x] Reference-photo consent is explicit; a stored profile can be deleted
  independently.
- [x] Preview UI includes source garments, a clear AI visualization disclosure,
  durable failure, and retry behavior.
- [x] Deterministic local normalization, hashing, chroma QA, and duplicate
  ranking conserve provider credits.
- [x] README, local setup, architecture, attribution, provider guardrails, and
  the local demo runbook are in the repository.

Run before a handoff or recording:

```bash
make test
make lint
make typecheck
make build
```

## Required before claiming the PRD definition of done

- [ ] Obtain the project owner's explicit authorization to use credentials,
  perform live provider tests, and deploy.
- [ ] Create a separate private B2 demo bucket or prefix with a
  least-privilege key, lifecycle policy, and CORS policy.
- [ ] Configure a separate production-like PostgreSQL database and apply the
  migration.
- [ ] Complete and retain the non-sensitive GMI capability record in
  [provider-spike.md](provider-spike.md); do not commit keys, signed URLs, or
  personal imagery.
- [ ] Select only account-tested GMI model IDs in the server secret store.
- [ ] Prove one live, GMI-backed cutout or selected-preview run through
  Genblaze into B2. Verify tenant ID, bounded retry/fallback behavior,
  parent-run lineage, object existence, and matching output hashes.
- [ ] Confirm that no signed source URL, personal reference media identifier,
  provider credential, or raw correction text appears in a persisted manifest
  or client-visible log.
- [ ] Import a consented demo wardrobe, review its source evidence, and prove
  a poor/occluded example is held rather than reconstructed as verified.
- [ ] Validate three live weather- and occasion-aware, approved-only looks and
  one selected preview with its exact source garment cards.
- [ ] Complete keyboard, mobile, empty-state, and failure-state checks.
- [ ] Deploy the web and API/worker with only server-side secrets, then test
  as a judge without developer credentials.
- [ ] Record the three-minute demo video and capture the actual deployment URL
  for the submission.

## Safe Devpost copy

Use the following only while the project remains in its current state:

> Fit Check is a provenance-aware digital wardrobe MVP that turns reviewed
> outfit photos into owned-only weather-aware recommendations and a selected
> AI-preview workflow. Its local demo keeps media handling deterministic and
> credit-free while the live Backblaze B2, Genblaze, and GMI Cloud path awaits
> an account-specific privacy and capability validation.

Do **not** claim that GMI, Genblaze, or B2 processed a real run until the
corresponding item above has been verified. When the live path is authorized
and tested, replace the caveat with the actual provider/model identifiers,
Genblaze pipeline details, B2 object evidence, and measured retry behavior.

## Recording and judge-accessibility checklist

- [ ] Use a consented, non-sensitive demo dataset or the synthetic local seed;
  never show a credential, signed URL, or private real-world source image
  without permission.
- [ ] Begin with the user problem, then show source evidence before the preview.
- [ ] Narrate “owned-only” and “human review” when showing recommendations and
  garment cards.
- [ ] Narrate the AI-preview limitations while the selected preview is visible.
- [ ] Open the provenance record and show source IDs, object key/hash, provider,
  model, run ID, parent-run ID, and manifest—not an unredacted prompt.
- [ ] State mock/local status candidly if live validation is still pending.
- [ ] If a live demo is approved later, record the B2/Genblaze/GMI evidence in
  the provider spike record before publishing a video or Devpost claim.

## Explicitly out of scope

Do not expand the submission build with calendar OAuth, shared closets,
shopping/affiliate flows, or video generation before the core B2/Genblaze/GMI
path and judge flow have been validated. Those are PRD stretch goals, not a
substitute for the source-to-preview MVP.
