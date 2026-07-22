# Fit Check

## Product Requirements Document

| Field | Value |
| --- | --- |
| Status | Build-ready hackathon PRD |
| Version | 1.0 |
| Product | Fit Check |
| Tagline | What to wear today, from clothes you actually own. |
| Primary challenge | Backblaze Generative AI Media Hackathon |
| Primary user | A person with a real wardrobe who wants faster, more confident daily outfit decisions |

---

## 1. Executive summary

Fit Check is a private, AI-powered digital wardrobe. A user uploads photographs of themselves wearing their own clothing. Fit Check identifies the distinct garments, creates reviewable catalog cutouts, organizes them into a durable wardrobe, recommends weather- and occasion-appropriate outfits, and renders a selected look as an AI virtual try-on preview.

The important distinction is trust. Fit Check does not present invented fashion inspiration as the user's wardrobe. Every garment, cutout, and generated look has visible provenance: the source photo(s), confidence, transformations, prompt, model, run identifier, and retry history. When a garment is too obscured to reconstruct honestly, Fit Check asks for a better photo instead of silently fabricating it.

The product's promise is:

> Help me wear more of what I already own, with a useful answer for today.

Fit Check is intentionally a production-minded generative-media workflow:

1. Media is ingested, normalized, hashed, and stored durably.
2. AI and deterministic processing turn source photos into structured garment assets.
3. A user reviews uncertain extraction decisions.
4. An outfit planner uses only approved wardrobe items plus weather and occasion context.
5. A virtual try-on preview is generated on demand.
6. Backblaze B2 stores original assets, derivatives, final media, and immutable provenance records.
7. Genblaze orchestrates provider calls, retries, fallback, storage, and run-level lineage.

---

## 2. Problem and opportunity

### User problem

Most people own more clothes than they regularly wear. Their closet is physically visible but digitally unsearchable: they cannot easily remember every item, reason about combinations, account for tomorrow's weather, or tell whether they are underusing expensive pieces. Existing outfit apps tend to require manual cataloging or recommend new purchases instead of making existing clothes more useful.

### Why current solutions fall short

| Current behavior | Consequence | Fit Check response |
| --- | --- | --- |
| A camera roll contains the wardrobe only indirectly. | Clothing is hard to search, reuse, and combine. | Turn uploaded outfit photos into a reviewable garment inventory. |
| Generic AI stylists invent clothing the user does not own. | Suggestions are attractive but impractical. | Generate recommendations only from approved inventory items. |
| Virtual try-on results are opaque. | Users cannot judge whether a result reflects their actual garments. | Show source evidence and label verified versus reconstructed assets. |
| Generated media is stored ad hoc. | Results are lost, hard to reproduce, and difficult to debug. | Store assets, metadata, manifests, and lineage in B2. |
| Users do not know what to wear for the day they actually have. | The tool remains a novelty. | Combine weather, occasion, preferences, and wear history into a daily decision. |

### Hackathon opportunity

Fit Check demonstrates a genuine generative-media application, not a single image prompt:

- A growing media archive of uploaded photos, transparent garment PNGs, thumbnail derivatives, try-on renders, and provenance manifests lives in Backblaze B2.
- Genblaze orchestrates multi-step media generation, model choice, retry/fallback, durable storage, and lineage.
- GMI Cloud supplies the primary AI models without requiring an OpenAI API key.
- The app has a clear user value proposition: reduce daily outfit friction and increase wardrobe utilization.

---

## 3. Product vision and principles

### Vision

Fit Check becomes a personal wardrobe memory and daily decision assistant: a person can ask, “What should I wear tomorrow?” and get a realistic, explainable answer based on clothes they own.

### Product principles

1. **Owned-first.** Outfit recommendations must consist of items in the user's approved wardrobe. The app may identify a wardrobe gap, but must never quietly substitute a product the user does not own.
2. **Evidence before aesthetics.** Preserve source-supported color, construction, material, and pattern. Prefer an incomplete inventory record to a fabricated garment.
3. **Human review for identity decisions.** AI can propose garment identity and duplicate matches; the user confirms merges, edits, and approvals.
4. **Generate on demand.** Do not spend credits generating every possible outfit or try-on. Cache reusable assets and render only selected looks.
5. **Provenance is a feature.** A user and a judge should be able to inspect how every generated media asset was produced.
6. **Privacy by default.** Wardrobe photos are personal. Assets remain private, are served through scoped URLs, and can be deleted.
7. **Useful today.** Weather and occasion-aware recommendations are the core differentiator, not an optional novelty.

---

## 4. Goals, non-goals, and success criteria

### Goals for the hackathon MVP

- Let a single user upload a batch of outfit photos and create a useful digital wardrobe.
- Extract 10–20 distinct garments with a reviewable workflow.
- Produce three weather- and occasion-aware outfit recommendations using only approved garments.
- Generate at least one AI try-on preview that is visibly linked to its source assets.
- Persist raw uploads, derived assets, generated images, metadata, and Genblaze manifests in Backblaze B2.
- Use Genblaze for meaningful orchestration of generative media steps and demonstrate fallback/retry behavior.
- Operate entirely without an OpenAI API key.
- Provide a polished, judge-accessible web experience and a three-minute demo path.

### Non-goals for the MVP

- Perfectly accurate 3D clothing simulation, fit prediction, sizing, or fabric physics.
- Automatic ingestion of an entire camera roll without review.
- Social-network, shared-roommate, or marketplace features.
- Shopping, affiliate commerce, or retail recommendations.
- Full Google/Outlook calendar OAuth integration.
- A video-first content creator suite.
- Multi-user wardrobe sharing and complex permissions.
- Medical, body-measurement, or sensitive body-image analysis.

### Success criteria

| Dimension | MVP target |
| --- | --- |
| Import completion | A test batch of 10 photos produces a review queue and at least 10 approved inventory items. |
| Fidelity | Every accepted cutout is traceable to source evidence; uncertain items are held for review. |
| Daily utility | The user can enter an occasion and receive three usable looks within two minutes after inventory is ready. |
| Media workflow | At least one end-to-end look creates B2-stored assets and a verifiable Genblaze manifest. |
| Reliability | Failed provider calls are surfaced clearly and retried or moved to a fallback path. |
| Cost control | No background batch creates unbounded generative-image jobs. |
| Demo quality | A judge can understand the full source-to-try-on workflow in roughly three minutes. |

---

## 5. Target users and jobs to be done

### Primary persona: the busy wardrobe owner

Someone who has a varied wardrobe, little time in the morning, and wants practical outfit suggestions. They are willing to spend a short setup session uploading photos if the app reduces future decision fatigue.

**Jobs to be done**

- “When I am getting dressed for work, dinner, or a weekend plan, help me choose an outfit that fits the weather and uses clothes I own.”
- “When I forget what is in my closet, help me rediscover items and combinations.”
- “Before I wear a combination I have not tried, show me a believable visual preview.”

### Secondary persona: the value-conscious wardrobe optimizer

A user who enters purchase price and wants to understand garment utilization.

**Jobs to be done**

- “Show me which pieces I wear, which are neglected, and how I can lower cost per wear.”
- “Tell me whether I have enough versatile outfits without encouraging another purchase.”

### Tertiary persona: the content-oriented user

A user who wants an occasional polished outfit card or short OOTD-style output.

**Jobs to be done**

- “Turn a look I am already wearing into a shareable visual.”

This is a stretch persona; it must not drive MVP scope.

---

## 6. Primary use cases

### UC-1: Build a wardrobe from existing outfit photos

1. The user uploads 8–15 photos.
2. Fit Check normalizes them and detects candidate garments.
3. The user reviews candidate crops, names items, rejects false positives, and confirms likely duplicates.
4. Fit Check creates clean catalog cutouts only for approved candidates.
5. The user sees an organized wardrobe gallery.

### UC-2: Decide what to wear tomorrow

1. The user selects or confirms a location.
2. Fit Check retrieves weather for the intended date and lets the user enter an occasion, for example “rainy commute, dinner after work.”
3. The planner selects compatible items from the approved wardrobe.
4. The user receives three ranked options with a short explanation.
5. The user marks an outfit as worn, saved, or not interested.

### UC-3: Preview a new combination

1. The user selects a recommendation.
2. The user chooses a reference photo or profile image.
3. Fit Check generates one AI try-on preview.
4. The result displays the specific garment assets used, disclosure language, and its provenance trail.

### UC-4: Recover from poor source imagery

1. The extractor identifies a garment that is covered by a coat, blended with another layer, or too small to verify.
2. Fit Check marks it “Needs a better photo” rather than generating a misleading inventory item.
3. The app provides capture guidance: front, back, full garment visible, even lighting, and minimal overlap.

### UC-5: Track wardrobe return on investment

1. The user optionally enters purchase price and purchase date for a garment.
2. Each worn outfit increments a garment's wear count.
3. The dashboard calculates cost per wear and highlights underused pieces.

---

## 7. MVP feature requirements

### 7.1 Onboarding and profile

**Requirements**

- Collect a display name and optional default location.
- Ask for consent before storing personal reference photos.
- Let the user add one or more reference photos for try-on previews.
- Explain that generated previews are visualizations, not sizing or fit guarantees.

**Acceptance criteria**

- A user can complete onboarding without entering a price, measurements, or calendar connection.
- A reference image can be deleted independently from wardrobe items.

### 7.2 Guided upload and import jobs

**Requirements**

- Support JPG, PNG, WebP, and HEIC where platform conversion is available.
- Upload directly to a private B2 location through a scoped upload URL.
- Normalize orientation, calculate SHA-256, record dimensions, and prevent duplicate raw uploads.
- Create an import job with visible stages: Uploaded, Inventorying, Awaiting Review, Extracting, Quality Check, Complete, Failed.
- Stream job progress to the UI.

**Acceptance criteria**

- Uploading a duplicate file does not create a second generation job.
- A failed image does not stop other photos from completing.
- The user can retry an individual failed candidate without rerunning the batch.

### 7.3 Garment inventory and review

**Requirements**

- Identify candidate garments with category, color, apparent material, pattern, source bounding box, confidence, and unresolved details.
- Allow the user to rename, recategorize, edit tags, reject, and approve candidates.
- Propose duplicate pairs using image similarity only as a review aid.
- Never auto-merge two generic garments merely because generated poses or colors look similar.
- Preserve source references for each canonical garment.

**Acceptance criteria**

- Every approved garment has at least one source reference.
- A user can reject an AI-proposed duplicate.
- A garment with inadequate evidence remains in a held state rather than being silently accepted.

### 7.4 Catalog cutout generation and quality assurance

**Requirements**

- Create one transparent RGBA PNG per approved garment, except established matching pairs such as shoes.
- Use a source-evidence prompt that excludes the wearer, skin, hair, other layers, props, hangers, and background.
- Generate against a removable chroma background when an alpha output is unavailable.
- Use deterministic chroma removal and technical validation.
- Store a visual QA result, including source crop, output image, warnings, and reviewer decision.

**Acceptance criteria**

- Final PNGs have a transparent alpha channel and transparent corners.
- Each item has visible padding and no clipped extremities.
- The system flags obvious body remnants, fused garments, opaque backgrounds, and unsupported construction.
- The user can regenerate a rejected cutout with corrected guidance.

### 7.5 Closet gallery and metadata editing

**Requirements**

- Display garments as filterable cards by category, color, season, status, and wear count.
- Allow editing of name, category, tags, price, purchase date, and notes.
- Show “verified source-backed,” “AI-reconstructed,” or “needs better photo” status.
- Support archive/delete actions.

**Acceptance criteria**

- A user can find all outerwear or all black tops quickly.
- Editing a garment does not overwrite its immutable source/provenance record.

### 7.6 Context-aware outfit recommendations

**Requirements**

- Retrieve weather by selected location and date.
- Accept a lightweight occasion/context prompt; calendar OAuth is not required for MVP.
- Rank outfits using weather suitability, category completeness, palette compatibility, user preferences, recent wear avoidance, and optional cost-per-wear optimization.
- Return three diverse options rather than near duplicates.
- Explain the recommendation in plain language.

**Acceptance criteria**

- A cold rainy-day request does not recommend shorts as the primary bottom without a user override.
- Every recommendation references only approved wardrobe items.
- Each proposed look is materially different from the other two.

### 7.7 Virtual try-on preview

**Requirements**

- Generate a preview only after a user selects an outfit.
- Use the user's chosen reference image plus the selected garment assets.
- Show a progress state and allow a retry with a different model or prompt.
- Show generated time, model, source garment cards, and a clear AI-preview disclosure.
- Store approved previews in B2 and allow download/share only through user-authorized URLs.

**Acceptance criteria**

- A preview is linked to the exact outfit item IDs used.
- The UI does not claim true size, drape, or purchase-ready accuracy.
- Provider failure returns an actionable error and does not lose the selected outfit.

### 7.8 Wear logging and wardrobe ROI

**Requirements**

- Let a user mark a suggested or manually assembled outfit as worn.
- Increment wear counts for contained garments.
- Calculate cost per wear when purchase price exists.
- Show most-worn, least-worn, and recently worn items.

**Acceptance criteria**

- A wear event is reversible.
- Cost per wear is not shown when price or wear count is missing.

### 7.9 Provenance explorer

**Requirements**

- Expose a compact “How this was made” panel on each generated asset.
- Include source asset IDs, source URLs available to the owner, transformations, provider/model, prompt policy, timestamps, SHA-256, run ID, parent run ID, and manifest URI.
- Redact sensitive prompt/details from shared links.
- Provide a developer view that can verify the manifest.

**Acceptance criteria**

- A judge can trace a final look back to source garment records.
- A developer can identify the provider/model that produced a failed or low-quality result.

---

## 8. User experience and screen map

### Primary navigation

| Screen | Purpose | MVP status |
| --- | --- | --- |
| Today | Weather-aware outfit recommendations and try-on entry point | Required |
| Import | Upload, pipeline status, candidate review, cutout approval | Required |
| Closet | Searchable wardrobe gallery and metadata editor | Required |
| Lookbook | Saved recommendations and generated previews | Required |
| Insights | Cost-per-wear and utilization summary | Required, lightweight |
| Settings | Location, profile images, data export/delete, model/debug settings | Required, minimal |

### Core interaction flow

~~~mermaid
flowchart LR
    A["Upload outfit photos"] --> B["Normalize, hash, store in B2"]
    B --> C["AI inventory proposal"]
    C --> D["User review and duplicate confirmation"]
    D --> E["Generate cutout and run QA"]
    E --> F["Approved digital closet"]
    F --> G["Weather + occasion outfit planner"]
    G --> H["User selects one look"]
    H --> I["Virtual try-on generation"]
    I --> J["B2 assets + Genblaze manifest"]
    J --> K["Save, wear log, or retry"]
~~~

### Import UX states

- **Upload ready:** drag/drop, paste, or select photos; capture recommendations shown before upload.
- **Inventorying:** show each source photo, file status, and a non-blocking progress indicator.
- **Review candidates:** present source crop next to structured attributes; actions are Approve, Edit, Reject, Hold, and Merge with.
- **Generating cutouts:** use an individual item queue, not one opaque batch spinner.
- **Quality review:** show source crop, cutout on checkerboard, technical status, and regenerate action.
- **Complete:** transition directly to the Closet gallery and show a count of accepted, held, and skipped items.

### Today screen behavior

- Top card: location, date, forecast, temperature, precipitation, and occasion field.
- Three outfit cards: names, garment thumbnails, weather rationale, and “Why this works.”
- Actions: Preview on me, Save, Wear it, Swap item, and Explain.
- A generated preview should not be created automatically for all three cards.

---

## 9. Technology architecture

### Recommended stack

| Layer | Recommendation | Rationale |
| --- | --- | --- |
| Web application | Next.js, React, TypeScript, Tailwind CSS | Fast, polished app UI and easy deployment. |
| API and orchestration | Python 3.11+, FastAPI, Pydantic | Genblaze is a Python SDK; FastAPI supports streaming job progress cleanly. |
| Generative workflow | Genblaze Core, Genblaze S3, Genblaze GMI Cloud adapter | Provider orchestration, B2 persistence, retries, manifests, lineage. |
| Primary AI provider | GMI Cloud | Uses the hackathon partner and the user's available credits. |
| Optional fallback provider | NVIDIA NIM via Genblaze | Free inference fallback for selected image/chat workloads when appropriate. |
| Object storage | Backblaze B2 private bucket | Raw uploads, media derivatives, generated outputs, manifests, logs. |
| Application database | PostgreSQL via Supabase or Neon | Durable metadata, job states, users, garment relationships, wear events. |
| Image processing | Pillow and/or Sharp; rembg/BiRefNet/SAM-family service | Cheap deterministic normalization, masking, alpha QA, duplicate ranking. |
| Background work | Database-backed worker process for MVP; queue abstraction for production | Provider jobs are asynchronous and should survive API restarts. |
| Real-time UI | Server-Sent Events initially | Simple progress stream from FastAPI to Next.js. |
| Weather | Open-Meteo forecast and geocoding APIs | No-cost, no-key starting point. |
| Deployment | Vercel for web plus Render, Fly.io, Railway, or similar for API/worker | Separates browser UI from Python and media workload. |

### Component architecture

~~~mermaid
flowchart TB
    U["Browser / Next.js"] --> API["FastAPI API"]
    API --> DB["PostgreSQL metadata"]
    API --> B2["Backblaze B2 private bucket"]
    API --> W["Import / generation worker"]
    W --> GB["Genblaze pipelines"]
    GB --> GMI["GMI Cloud"]
    GB --> NIM["NVIDIA NIM fallback (optional)"]
    GB --> B2
    W --> CV["Local CV and image QA"]
    CV --> B2
    API --> WX["Open-Meteo"]
~~~

### Architectural decisions

1. **Keep provider keys server-side.** GMI explicitly warns not to expose API keys in client-side code. The browser talks only to the Fit Check API.
2. **Keep B2 separate from metadata.** B2 stores large binary media and immutable manifests; PostgreSQL stores relational state and user-facing metadata.
3. **Use direct-to-B2 uploads.** The browser receives a short-lived, scoped upload URL so the API does not become a large-media proxy.
4. **Use private assets by default.** When a model needs an input image URL, create a short-lived provider-compatible URL instead of making wardrobe photos publicly accessible.
5. **Model selection is configurable.** Do not hard-code a GMI model assumption. The application will run a model capability smoke test and store configured model IDs in server-side settings.

---

## 10. Genblaze and B2 implementation plan

### Required Genblaze usage

Fit Check must use Genblaze as real orchestration, not merely import it.

| Pipeline | Steps | Output |
| --- | --- | --- |
| Import pipeline | inventory proposal → source crop references → cutout generation → B2 sink → manifest | Approved garment catalog asset(s) and provenance |
| Try-on pipeline | assemble selected garment references → virtual try-on/edit generation → QA/thumbnail → B2 sink → manifest | Saved generated preview and provenance |
| Optional Fit Check clip | still preview → image-to-video → narration/music → compose → B2 sink | Shareable short media output |

### Pipeline behavior

- Use a shared Genblaze ObjectStorageSink backed by B2.
- Give every run a tenant/user ID and pipeline slug.
- Persist the resulting canonical manifest with the generated asset.
- Use parent run IDs to link a regenerated asset or try-on preview to the original garment/import run.
- Configure bounded retries for transient provider errors.
- Configure a model fallback chain only after source quality is confirmed; a fallback must not hide a fidelity failure.
- Stream pipeline events into the import and preview screens.
- Record model, parameters, source asset references, cost estimate when available, and error taxonomy in application metadata.

### B2 object organization

~~~text
fit-check/
  users/{user_id}/
    uploads/{upload_id}/original.{ext}
    uploads/{upload_id}/normalized.jpg
    garments/{garment_id}/source-crops/{crop_id}.jpg
    garments/{garment_id}/masks/{mask_id}.png
    garments/{garment_id}/cutouts/{version}.png
    garments/{garment_id}/thumbnails/{version}.webp
    looks/{look_id}/renders/{version}.png
    looks/{look_id}/thumbnails/{version}.webp
    manifests/{run_id}.json
    exports/{export_id}.zip
~~~

### Provenance record

Every generated cutout or preview should retain:

- asset ID and B2 object key;
- SHA-256 of input and output;
- user ID and privacy scope;
- source upload/crop IDs;
- garment and outfit IDs;
- model provider and model identifier;
- prompt template version and redacted prompt;
- generation parameters and seed when the provider returns one;
- Genblaze run ID, step ID, parent run ID, manifest URI, and manifest hash;
- created, retried, approved, archived, and deleted timestamps;
- evaluator/user QA outcome.

---

## 11. Model and credit strategy

### Important constraint

Fit Check will not use GPT Image or Codex as a production runtime dependency. Codex is used to build, test, and maintain the application; the deployed app uses GMI Cloud and optional open/free provider paths.

### Provider strategy

| Task | Primary approach | Low-cost/fallback approach | Notes |
| --- | --- | --- | --- |
| Garment inventory | GMI-hosted multimodal/vision-capable chat model returning JSON | Manual candidate entry when model confidence is low | Require source bounding boxes and confidence. |
| Crop and normalization | Pillow/Sharp | Same | No generative cost. |
| Mask/background separation | rembg/BiRefNet or SAM-family tooling | Manual review/hold | Useful for assistance; not sufficient alone for occluded garment reconstruction. |
| Cutout reconstruction | GMI image model with reference-image/edit capability | Do not generate; hold for better photo | Choose actual model after GMI account smoke test. |
| Duplicate suggestion | pHash + CLIP/SigLIP-style embedding ranking | Manual comparison | Never auto-delete. |
| Outfit plan | Rules plus GMI chat model structured JSON | Deterministic rules-only plan | Rules constrain use to owned inventory. |
| Virtual try-on | GMI-hosted VTON model if available | Reference-image edit model; label as AI preview | A generic image model is not a literal fit simulation. |
| Optional video | GMI image-to-video only after core is complete | No video | Avoid draining credits before the core works. |

### Required model selection spike

Before building final provider code, run a small test using the user's GMI account:

1. List models available to the account.
2. Identify one low-cost chat/vision model that accepts images and JSON-mode responses.
3. Identify one image model that accepts one or more reference images.
4. Test a single garment reconstruction from a cropped source image.
5. Test a single user + garment try-on/edit request.
6. Capture latency, cost, quality, error response shape, accepted input URL format, and output URL behavior.
7. Select a default and a fallback only after these tests pass.

The GMI model catalog and capabilities can change, so this test is a feature of the implementation rather than a one-time manual assumption.

### Credit controls

- Generate no cutout until the user approves a candidate.
- Use a source hash to avoid repeating work after a refresh.
- Batch local analysis but cap concurrent paid image jobs.
- Create one try-on preview for the user-selected look, never all recommendations by default.
- Limit regeneration attempts per item and require an edited correction reason after repeated failures.
- Record estimated or actual per-run cost where the provider exposes it.
- Set a per-user daily generation quota in demo and production settings.

---

## 12. Data model

### Core entities

| Entity | Key fields | Notes |
| --- | --- | --- |
| User | id, display_name, location, consent timestamps | Auth provider ID maps to internal user ID. |
| ModelProfile | id, user_id, source_image_key, status | Reference image(s) used only for previews. |
| Upload | id, user_id, b2_key, sha256, dimensions, source_date, status | Immutable raw-upload record. |
| ImportJob | id, user_id, status, progress, error_code, run_id | Parent job for a batch. |
| GarmentCandidate | id, upload_id, bbox, attributes, confidence, status | Proposed item before approval. |
| Garment | id, user_id, name, category, colors, tags, price, wear_count, canonical_asset_id | User-approved wardrobe item. |
| GarmentEvidence | id, garment_id, upload_id, crop_key, role, notes | Supports source-backed identity. |
| GarmentAsset | id, garment_id, kind, b2_key, sha256, version, QA status, run_id | Cutout, mask, thumbnail, etc. |
| DuplicateReview | id, garment_a_id, garment_b_id, score, status | AI ranking plus human decision. |
| OutfitPlan | id, user_id, weather_snapshot, occasion, score, reasoning, status | One candidate outfit. |
| OutfitItem | outfit_id, garment_id, role | Top, bottom, outerwear, shoes, accessory. |
| TryOnRender | id, outfit_id, profile_id, b2_key, run_id, status | Generated visual preview. |
| WearEvent | id, user_id, outfit_id, worn_on, notes | Increments wear counts; reversible. |
| ProvenanceLink | id, entity_type, entity_id, manifest_key, manifest_hash, parent_run_id | Fast UI lookup to Genblaze provenance. |

### Garment status values

- candidate
- awaiting_review
- approved
- generating
- qa_review
- ready
- needs_better_photo
- duplicate_pending
- archived
- deleted

### Outfit status values

- proposed
- saved
- preview_generating
- preview_ready
- worn
- rejected

---

## 13. API surface

The initial API should be versioned under /v1 and use JSON except for signed upload/download endpoints.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | /v1/uploads/presign | Request a scoped B2 upload URL. |
| POST | /v1/imports | Create an import job from uploaded asset IDs. |
| GET | /v1/imports/{id} | Retrieve job state and candidate counts. |
| GET | /v1/imports/{id}/events | Stream Server-Sent Events for job progress. |
| PATCH | /v1/candidates/{id} | Approve, edit, reject, hold, or merge a candidate. |
| POST | /v1/garments/{id}/generate-cutout | Generate or regenerate an approved garment cutout. |
| GET | /v1/garments | Filter/search wardrobe items. |
| PATCH | /v1/garments/{id} | Edit user-controlled metadata. |
| POST | /v1/outfits/recommend | Produce weather- and occasion-aware looks. |
| POST | /v1/outfits/{id}/render | Create one try-on preview. |
| POST | /v1/outfits/{id}/wear | Create or reverse a wear event. |
| GET | /v1/provenance/{entity_type}/{id} | Retrieve a redacted provenance graph. |
| DELETE | /v1/users/me/data | Request account and media deletion. |

### Error contract

Every error response should include:

- stable code, for example PROVIDER_TIMEOUT or SOURCE_TOO_OBSCURED;
- user-safe message;
- retryable boolean;
- affected entity/job ID;
- optional recommended action;
- internal correlation/run ID for support and debugging.

---

## 14. Outfit recommendation logic

The first version should not delegate all decision-making to an LLM. Use deterministic constraints first, then allow an LLM to explain and diversify a valid set.

### Candidate-building rules

1. Choose exactly one primary top and bottom, or one dress/jumpsuit.
2. Include outerwear when weather threshold or precipitation suggests it.
3. Include footwear if approved shoes exist; otherwise disclose that footwear is not cataloged.
4. Exclude incompatible categories and archived/unavailable items.
5. Prefer garments tagged as seasonally suitable.
6. Penalize pieces worn very recently when alternatives exist.
7. Give a small boost to low-use but compatible items when the user enables utilization mode.
8. Never recommend a garment that is only a rejected candidate or needs a better photo.

### LLM responsibility

The model receives a constrained, structured wardrobe candidate list and returns:

- three outfit IDs assembled from valid garment IDs;
- confidence and weather suitability;
- a brief “why this works” explanation;
- palette/style notes;
- a refusal/explanation if the wardrobe lacks a safe suitable combination.

The server validates every returned garment ID before exposing a recommendation.

---

## 15. Security, privacy, and responsible AI

### Privacy requirements

- Keep all uploaded and generated wardrobe assets private by default.
- Use least-privilege B2 keys and per-environment buckets.
- Use expiring, scoped URLs for browser access and third-party model input.
- Never log raw signed URLs, provider keys, or full unredacted user prompts to client analytics.
- Provide deletion that removes database references, B2 objects, derived thumbnails, and manifests according to documented retention behavior.
- Separate personal reference images from generic garment assets in object keys and permissions.
- Do not expose one user's media to another user through predictable object paths.

### Responsible-generation requirements

- Obtain consent before generating a preview that uses a person's reference image.
- Disclose that previews are AI-generated visualizations and may not reproduce actual fit, size, fabric drape, body shape, or garment details exactly.
- Do not infer sensitive traits from uploaded images.
- Do not present reconstructed details as verified if they were not visible in the source.
- Provide a no-generation/manual mode for users who want only wardrobe organization.

---

## 16. Reliability and failure handling

| Failure mode | User experience | System action |
| --- | --- | --- |
| Corrupt or unsupported upload | Clear file-level error | Preserve other batch items; invite retry. |
| Garment too small or occluded | “Needs a better photo” state | Do not spend image-generation credits. |
| Duplicate ambiguity | Side-by-side review screen | Keep both unless user confirms merge. |
| GMI timeout or queue error | Item-level retry notice | Retry with bounded exponential backoff; retain job state. |
| Model output has opaque background/body remnants | QA rejection with reason | Regenerate once with correction context or request better source. |
| Virtual try-on failure | Keep outfit selection and show retry | Offer configured fallback or defer. |
| B2 upload failure | “Saving securely failed” state | Do not mark media as complete until hash and object presence validate. |
| App/API restart | Job resumes from database state | Do not rely on in-memory tasks as the source of truth. |

### Quality gates

For each catalog cutout, validate:

- PNG format and RGBA mode;
- transparent corners and substantial transparent border;
- non-empty content with safe visible padding;
- no significant chroma-colored halo;
- source-supported category and visible properties;
- absence of person, skin, hair, adjacent garments, props, or text hallucinations;
- approved human review for uncertain items.

---

## 17. Non-functional requirements

### Performance

- Direct uploads should begin promptly and report per-file progress.
- The initial wardrobe gallery should load thumbnails, not full-resolution PNGs.
- A weather recommendation request should return within 10 seconds excluding optional generation.
- The UI should clearly communicate that image generation may take longer and continue asynchronously.

### Accessibility

- Keyboard-operable review controls.
- Descriptive alt text for garment cards and generated images.
- Color should not be the only indicator of job status.
- Sufficient contrast and mobile-friendly target sizes.

### Observability

- Structured logs include request ID, user ID hash, job ID, run ID, provider, model, latency, and error class.
- Track job completion rate, failed provider calls, retries, generation cost, user approvals, and try-on conversion.
- Add a hidden developer/debug panel for the hackathon demo.

### Scalability

- Keep worker execution stateless; B2 and PostgreSQL hold durable state.
- Limit provider concurrency per user and globally.
- Store content-addressed hashes to avoid redundant media processing.
- Use lifecycle policies for temporary source crops and non-approved artifacts after a defined retention period.

---

## 18. Deployment plan

### Environments

| Environment | Purpose | Data policy |
| --- | --- | --- |
| Local development | Feature work and smoke tests | Local database/emulator or isolated development B2 prefix. |
| Demo/staging | Judge-accessible deployment | Separate B2 bucket or prefix; controlled sample user/media. |
| Production | Future multi-user use | Separate credentials, database, and private B2 bucket. |

### Required environment variables

~~~dotenv
APP_ENV=development
WEB_ORIGIN=http://localhost:3000
DATABASE_URL=

B2_KEY_ID=
B2_APP_KEY=
B2_BUCKET=
B2_REGION=
B2_PREFIX=fit-check

GMI_API_KEY=
GMI_ORG_ID=
GMI_VISION_MODEL=
GMI_IMAGE_MODEL=
GMI_TRYON_MODEL=

NVIDIA_API_KEY=
NVIDIA_FALLBACK_IMAGE_MODEL=

WEATHER_PROVIDER=open-meteo
SENTRY_DSN=
~~~

Only variables needed by enabled providers should be required. No secrets are committed to the repository.

### Deployment sequence

1. Deploy PostgreSQL and apply migrations.
2. Create private B2 bucket, least-privilege application key, CORS rule, and lifecycle policy.
3. Deploy FastAPI API and worker with environment secrets.
4. Deploy Next.js web application with API base URL only.
5. Run a GMI model capability smoke test.
6. Import demo assets and validate the full source-to-preview path.
7. Run a public-judge account test without developer credentials.

---

## 19. Testing strategy

### Automated tests

- Unit tests for garment category validation, outfit rules, cost-per-wear math, object-key generation, and source-hash dedupe.
- API tests for authorization, upload URL scope, user isolation, job state transitions, and error contracts.
- Pipeline tests using mocked GMI responses and a local/S3-compatible storage fixture.
- Contract tests for provider model parameters and output parsing.
- Image QA tests for RGBA alpha, padding, and chroma removal.
- End-to-end browser test for upload → candidate review → closet → outfit → preview job state.

### Manual media QA set

Prepare a small, consented test dataset containing:

- clean full-body outfit images;
- layered outfits;
- repeated garments across photos;
- similar-looking but distinct black/white tops;
- shoes and accessories;
- poor-quality/partially obscured examples.

The test set should prove that the app can distinguish “ready,” “needs review,” and “needs a better photo.”

---

## 20. Product analytics and success metrics

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Import approval rate | Approved garments divided by candidates | Measures inventory usefulness and extraction quality. |
| Better-photo rate | Items held for improved source divided by candidates | Surfaces capture friction and fidelity limits honestly. |
| Duplicate correction rate | User overrides divided by duplicate proposals | Tracks dedupe quality without unsafe auto-merging. |
| Recommendation save/wear rate | Saved or worn looks divided by recommendations viewed | Measures daily utility. |
| Preview conversion | Try-on renders divided by selected looks | Indicates whether previews add value. |
| Median job completion time | Upload-to-ready and render-to-ready durations | Tracks production readiness. |
| Cost per useful asset | Provider spend divided by approved cutouts/renders | Keeps credit use disciplined. |
| Pipeline recovery rate | Successful retries divided by retryable failures | Demonstrates reliable orchestration. |

---

## 21. Build plan and milestones

### Milestone 0: Foundation and provider spike

- Create monorepo, CI, formatting, local environment, and deployment placeholders.
- Create B2 bucket/configuration and database schema.
- Port the Genblaze/B2 storage pattern from the official sample.
- Test GMI account model availability and one image-generation request.
- Add a mock provider so contributors can run the UI without paid credentials.

**Exit criteria:** a generated or mocked asset is stored in B2 with a provenance record.

### Milestone 1: Import and closet

- Build upload, import job, candidate review, garment gallery, and metadata editing.
- Implement deterministic image normalization, source hashing, crop storage, and basic duplicate review.
- Connect a GMI vision/inventory path and cutout generation path.
- Implement transparent cutout QA and user approval.

**Exit criteria:** a real test batch creates an approved B2-backed wardrobe.

### Milestone 2: Today and outfit logic

- Add weather integration, occasion input, rule-based candidate generator, and structured LLM explanation.
- Add saved outfits and wear logging.
- Add cost-per-wear calculations.

**Exit criteria:** a user can choose among three valid looks made entirely from owned garments.

### Milestone 3: Virtual try-on and provenance

- Add user reference image handling and the selected-look render job.
- Test GMI VTON/edit path, fallback behavior, and AI-preview disclosure.
- Build provenance drawer and developer verification view.

**Exit criteria:** one selected outfit produces a B2-stored preview with a linked Genblaze manifest.

### Milestone 4: Polish, deployment, and submission

- Refine empty, failure, and review states.
- Improve visual design and mobile behavior.
- Seed a clear demo account and record a three-minute walkthrough.
- Complete README, architecture diagram, provider/model list, and Devpost content.

**Exit criteria:** a judge can complete the happy path without local setup.

### Stretch goals, only after MVP is stable

- Import a local .ics calendar file, then Google/Outlook OAuth.
- Wardrobe gap finder.
- Shared closet/borrowing flow.
- 5-second narrated Fit Check clip using image-to-video and TTS.
- More robust VTON custom deployment on GMI infrastructure.

---

## 22. Three-minute demo script

| Time | Demonstration |
| --- | --- |
| 0:00–0:20 | State the problem: “I own plenty of clothes but still do not know what to wear.” |
| 0:20–0:50 | Upload a small batch and show B2-backed, live import stages. |
| 0:50–1:20 | Review an extracted garment, show source crop versus cutout, and explain verified/reconstructed status. |
| 1:20–1:45 | Open Today: show New York/New Jersey weather plus a “rainy workday” occasion and three owned-only looks. |
| 1:45–2:15 | Select one look and generate/view the try-on preview. |
| 2:15–2:40 | Open the provenance drawer: source photos, model/provider, B2 object, Genblaze run, manifest, and retry visibility. |
| 2:40–3:00 | Show cost-per-wear or wear logging, then summarize B2 + Genblaze + GMI usage and production path. |

---

## 23. Devpost submission outline

### One-line project description

Fit Check turns real outfit photos into a private, provenance-aware digital wardrobe that recommends weather-appropriate looks and previews them on you using the clothes you already own.

### Providers and models section

List actual selected models after the Milestone 0 smoke test. Do not claim models that were not exercised. Include:

- GMI Cloud model used for inventory/structured vision;
- GMI Cloud model used for garment reconstruction;
- GMI Cloud VTON/edit model used for preview, if applicable;
- NVIDIA NIM fallback model, if enabled;
- local deterministic tooling used for masking, QA, and duplicate ranking.

### Backblaze B2 usage section

Explain that B2 stores:

- original user uploads;
- normalized photos and source crops;
- generated transparent garment PNGs and thumbnails;
- selected outfit previews and optional videos;
- job logs/metadata exports where appropriate;
- Genblaze manifests and immutable provenance artifacts.

### Genblaze usage section

Explain that Genblaze:

- orchestrates cutout and preview generation;
- persists generated assets and manifests into B2;
- records model/prompt/parameter/source lineage;
- supports provider-specific polling, retry, and fallback;
- links regenerated assets with parent run IDs;
- makes output artifacts reproducible and inspectable.

---

## 24. Reference implementations and attribution

Fit Check should borrow patterns rather than blindly copy incompatible infrastructure.

- [Genblaze](https://github.com/backblaze-labs/genblaze): Python pipeline SDK with B2/S3 storage, provenance manifests, provider adapters, retry/fallback, and replay support.
- [Genblaze multi-provider sample](https://github.com/backblaze-labs/genblaze-gen-media-multi-provider-sample): useful Next.js + FastAPI structure, provider catalog, B2-first asset storage, SSE progress, and media-pipeline examples.
- [tandpfun/wardrobe](https://github.com/tandpfun/wardrobe): useful import/review UI, garment schema, catalog UX, and chroma QA inspiration. It is MIT-licensed but OpenAI-specific and local-first, so its OpenAI endpoints and storage design must be replaced.
- [GMI Cloud API documentation](https://docs.gmicloud.ai/): use account-specific model listing and provider documentation during the model capability spike.

If source code is copied from an MIT-licensed project, retain its copyright notice and license in the Fit Check repository. Do not copy personal/sample assets without permission.

---

## 25. Open decisions to resolve during implementation

1. Which exact GMI image and vision models are available to the project account and accept the required reference inputs?
2. Is a usable VTON model available through GMI's request queue, or should MVP use a generic image-edit preview with clear disclosure?
3. Which B2 region, bucket naming convention, CORS policy, and retention policy should be used?
4. Will the hackathon app be single-user/demo-only or use passwordless authentication?
5. Will PostgreSQL be hosted through Supabase, Neon, or another free-tier provider?
6. Which deployment platform best supports a long-running Python worker within the available budget?
7. What consented demo images will be used for the public judge experience?

---

## 26. Definition of done for the hackathon submission

Fit Check is ready to submit when:

- a deployed URL is available to judges;
- the app imports real photos into a reviewable wardrobe;
- B2 contains raw inputs, generated cutouts, preview assets, and provenance manifests;
- Genblaze is used in actual import and/or try-on generation runs;
- at least one GMI-backed generation path works in the deployed app;
- the app shows weather-aware, owned-only recommendations;
- one generated preview can be traced back to its source garments;
- a README contains local setup, provider/model choices, B2/Genblaze explanation, architecture, and test instructions;
- the repository includes all necessary attribution and excludes secrets;
- a concise three-minute demo video tells the complete user and infrastructure story.

