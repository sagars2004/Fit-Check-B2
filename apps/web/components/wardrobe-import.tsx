"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  type Candidate,
  type CandidateReview,
  type DemoWardrobeSeed,
  type DuplicateReview,
  type Garment,
  type GarmentUpdate,
  type ImportJob,
  createImport,
  decideDuplicateReview,
  generateCutout,
  getCandidates,
  getDuplicateReviews,
  getGarments,
  getHealth,
  getEventSourceUrl,
  reviewCutout,
  reviewCandidate,
  seedDemoWardrobe,
  updateGarment,
  uploadPhotos,
} from "../lib/api";

type LoadState = "loading" | "ready" | "error";

const importStages = ["uploaded", "inventorying", "awaiting_review", "extracting", "quality_check", "complete"];

export function WardrobeImport() {
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [garments, setGarments] = useState<Garment[]>([]);
  const [duplicateReviews, setDuplicateReviews] = useState<DuplicateReview[]>([]);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [uploading, setUploading] = useState(false);
  const [activeCandidate, setActiveCandidate] = useState<string | null>(null);
  const [activeGarment, setActiveGarment] = useState<string | null>(null);
  const [activeCutout, setActiveCutout] = useState<string | null>(null);
  const [activeDuplicateReview, setActiveDuplicateReview] = useState<string | null>(null);
  const [viewingGarmentId, setViewingGarmentId] = useState<string | null>(null);
  const [canSeedDemo, setCanSeedDemo] = useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [demoSeed, setDemoSeed] = useState<DemoWardrobeSeed | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const [candidateItems, garmentItems, duplicateItems] = await Promise.all([
        getCandidates(),
        getGarments(),
        getDuplicateReviews(),
      ]);
      setCandidates(candidateItems);
      setGarments(garmentItems);
      setDuplicateReviews(duplicateItems);
      setLoadState("ready");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Unable to load the local wardrobe.");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (viewingGarmentId) {
      document.body.classList.add("viewer-open");
    } else {
      document.body.classList.remove("viewer-open");
    }
    return () => document.body.classList.remove("viewer-open");
  }, [viewingGarmentId]);

  useEffect(() => {
    void getHealth()
      .then((health) => {
        // The seed endpoint is intentionally local-mock-only. Keep this affordance
        // absent for B2-backed or live-provider configurations rather than relying
        // on a rejected request to protect a real wardrobe.
        setCanSeedDemo(health.provider_mode === "mock" && health.storage_mode === "local");
      })
      .catch(() => setCanSeedDemo(false));
  }, []);

  useEffect(() => {
    if (!importJob?.id || importJob.progress >= 100) return;
    const sseUrl = getEventSourceUrl(`/v1/imports/${importJob.id}/events`);
    const source = new EventSource(sseUrl);
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (typeof payload.progress === "number") {
          setImportJob((prev) =>
            prev ? { ...prev, progress: payload.progress, status: payload.stage ?? prev.status } : prev
          );
        }
        if (payload.progress >= 100 || payload.stage === "complete" || payload.stage === "awaiting_review") {
          source.close();
          void refresh();
        }
      } catch {
        // Safe JSON parse error handling
      }
    };
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [importJob?.id, importJob?.progress, refresh]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (files.length === 0) {
      setError("Choose at least one JPG, PNG, or WebP photo first.");
      return;
    }
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await uploadPhotos(files);
      if (result.uploads.length > 0) {
        const job = await createImport(result.uploads.map((upload) => upload.upload_id));
        setImportJob(job);
        setNotice(
          `${job.candidate_count} review candidate${job.candidate_count === 1 ? "" : "s"} ready. ` +
            "Nothing becomes a wardrobe item until you approve it.",
        );
      }
      if (result.errors.length > 0) {
        setError(result.errors.join(" "));
      }
      setFiles([]);
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The import could not start.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSeedDemo() {
    setIsSeedingDemo(true);
    setError(null);
    setNotice(null);
    try {
      const seeded = await seedDemoWardrobe();
      setDemoSeed(seeded);
      await refresh();
      setNotice(
        seeded.created
          ? `Safe demo wardrobe loaded with ${seeded.approved_garment_count} approved items.`
          : `Safe demo wardrobe is already ready with ${seeded.approved_garment_count} approved items.`,
      );
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The safe demo wardrobe could not be loaded. Your existing closet was not changed.",
      );
    } finally {
      setIsSeedingDemo(false);
    }
  }

  async function handleReview(candidateId: string, review: CandidateReview) {
    setActiveCandidate(candidateId);
    setError(null);
    try {
      const updated = await reviewCandidate(candidateId, review);
      const label = review.action === "approve" ? "Added to your closet" : review.action;
      setNotice(`${label}: ${updated.attributes.name_suggestion ?? "review candidate"}.`);
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That review decision could not be saved.");
    } finally {
      setActiveCandidate(null);
    }
  }

  async function handleGarmentUpdate(garmentId: string, update: GarmentUpdate) {
    setActiveGarment(garmentId);
    setError(null);
    try {
      const updated = await updateGarment(garmentId, update);
      setNotice(`Updated ${updated.name}; its source evidence was left unchanged.`);
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That garment update could not be saved.");
    } finally {
      setActiveGarment(null);
    }
  }

  async function handleGenerateCutout(garmentId: string) {
    setActiveCutout(garmentId);
    setError(null);
    try {
      const asset = await generateCutout(garmentId);
      setNotice(
        asset.qa_status === "awaiting_review"
          ? "Source-linked cutout passed automated alpha QA. Review it before it becomes canonical."
          : "The source image could not pass conservative alpha QA. It was held; use a clearer photo.",
      );
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The cutout QA run could not start.");
    } finally {
      setActiveCutout(null);
    }
  }

  async function handleCutoutReview(garmentId: string, assetId: string, action: "approve" | "reject") {
    setActiveCutout(assetId);
    setError(null);
    try {
      await reviewCutout(garmentId, assetId, action);
      setNotice(
        action === "approve"
          ? "Approved source-backed cutout. Any visual matches remain review-only suggestions."
          : "Cutout rejected. This item is marked as needing a better source photo.",
      );
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That cutout decision could not be saved.");
    } finally {
      setActiveCutout(null);
    }
  }

  async function handleDuplicateDecision(
    reviewId: string,
    action: "keep_separate" | "mark_likely_duplicate",
  ) {
    setActiveDuplicateReview(reviewId);
    setError(null);
    try {
      await decideDuplicateReview(reviewId, action);
      setNotice(
        action === "keep_separate"
          ? "Kept both garments. No inventory data was changed."
          : "Marked as a likely duplicate for your review. No inventory data was changed.",
      );
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That duplicate decision could not be saved.");
    } finally {
      setActiveDuplicateReview(null);
    }
  }

  const visibleGarments = useMemo(() => {
    const term = filter.trim().toLowerCase();
    if (!term) return garments;
    return garments.filter(
      (garment) =>
        garment.name.toLowerCase().includes(term) ||
        garment.category.toLowerCase().includes(term) ||
        garment.colors.some((color) => color.toLowerCase().includes(term)) ||
        garment.tags.some((tag) => tag.toLowerCase().includes(term)),
    );
  }, [filter, garments]);
  const approvedGarmentCount = garments.filter((garment) => garment.status === "approved").length;
  const pendingDuplicateReviews = duplicateReviews.filter((review) => review.status === "pending");

  return (
    <section
      aria-busy={loadState === "loading" || uploading || isSeedingDemo}
      aria-labelledby="wardrobe-heading"
      className="wardrobe-workbench"
      id="closet"
      tabIndex={-1}
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Milestone 1 · import and closet</p>
          <h2 id="wardrobe-heading">Build a closet you can trust.</h2>
        </div>
        <span className="status-pill status-review">
          {loadState === "loading"
            ? "Loading private closet"
            : `${approvedGarmentCount} approved item${approvedGarmentCount === 1 ? "" : "s"}`}
        </span>
      </div>

      <p className="workbench-copy">
        Upload outfit photos privately, then review the preserved source crop before it enters your
        wardrobe. Fit Check never calls a guessed crop a verified cutout, and it never auto-merges
        similar clothes.
      </p>

      {canSeedDemo ? (
        <section className="demo-seed-panel" aria-labelledby="demo-seed-heading">
          <div>
            <p className="eyebrow">Quick demo · local mock mode</p>
            <h3 id="demo-seed-heading">Need a safe wardrobe to review?</h3>
            <p>
              Load an idempotent sample closet with approved source-backed garments and one item
              held for a better photo. It uses no cloud credentials and never creates a reference photo.
            </p>
          </div>
          <button
            className="secondary-button"
            disabled={isSeedingDemo}
            onClick={() => void handleSeedDemo()}
            type="button"
          >
            {isSeedingDemo ? "Loading safe demo…" : "Load safe demo wardrobe"}
          </button>
        </section>
      ) : null}

      {demoSeed ? (
        <section className="demo-seed-result" aria-labelledby="demo-seed-result-heading">
          <div>
            <p className="eyebrow">Demo wardrobe ready</p>
            <h3 id="demo-seed-result-heading">
              {demoSeed.approved_garment_count} approved owned item{demoSeed.approved_garment_count === 1 ? "" : "s"} are ready to plan.
            </h3>
            <p>
              {demoSeed.disclosure} One seeded item remains held for a better photo and is excluded from recommendations.
            </p>
            <p className="demo-seed-note">{demoSeed.reference_photo_requirement}</p>
          </div>
          <a className="primary-link" href="#today">Continue to Today</a>
        </section>
      ) : null}

      <form className="upload-panel" onSubmit={(event) => void handleUpload(event)}>
        <label className="drop-zone" htmlFor="outfit-photos">
          <span className="drop-icon" aria-hidden="true">↑</span>
          <span>
            <strong>Choose outfit photos</strong>
            <small>JPG, PNG, or WebP · private storage · up to 15 MB each</small>
          </span>
          <input
            id="outfit-photos"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.target.files ?? []))}
            type="file"
          />
        </label>
        <div className="upload-actions">
          <p aria-live="polite">
            {files.length === 0
              ? "Start with clear outfit photos. You will review every proposed item."
              : `${files.length} photo${files.length === 1 ? "" : "s"} selected: ${files.map((file) => file.name).join(", ")}`}
          </p>
          <button className="primary-button" disabled={uploading || files.length === 0} type="submit">
            {uploading ? "Saving + inventorying…" : "Create review queue"}
          </button>
        </div>
      </form>

      {notice ? <p className="success-message" role="status">{notice}</p> : null}
      {error ? (
        <div className="error-message" role="alert">
          <p>{error}</p>
          {loadState === "error" ? (
            <button className="inline-retry-button" onClick={() => void refresh()} type="button">
              Try loading the closet again
            </button>
          ) : null}
        </div>
      ) : null}

      {importJob ? <ImportProgress job={importJob} /> : null}

      <div className="review-header">
        <div>
          <p className="eyebrow">Review queue</p>
          <h3>Evidence first, identity second.</h3>
        </div>
        <span>{candidates.filter((candidate) => candidate.status === "awaiting_review").length} awaiting review</span>
      </div>

      {loadState === "loading" ? <p className="empty-state">Loading local review records…</p> : null}
      {loadState === "ready" && candidates.length === 0 ? (
        <p className="empty-state">Your first source crop will appear here after import.</p>
      ) : null}
      <div className="candidate-grid">
        {candidates.map((candidate) => (
          <CandidateCard
            candidate={candidate}
            isSaving={activeCandidate === candidate.id}
            key={candidate.id}
            onReview={handleReview}
          />
        ))}
      </div>

      <div className="closet-heading">
        <div>
          <p className="eyebrow">Owned wardrobe</p>
          <h3>Owned items, with the source still visible.</h3>
        </div>
        <label className="search-field">
          <span className="sr-only">Filter wardrobe</span>
          <input
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter by name, color, or tag"
            value={filter}
          />
        </label>
      </div>

      {loadState === "ready" && visibleGarments.length === 0 ? (
        <p className="empty-state">Approve a source-backed candidate to add it to this closet.</p>
      ) : null}
      <div className="closet-grid">
        {visibleGarments.map((garment) => (
          <GarmentCard
            garment={garment}
            isCutoutSaving={activeCutout === garment.id || garment.cutouts.some((asset) => asset.id === activeCutout)}
            isSaving={activeGarment === garment.id}
            key={garment.id}
            onGenerateCutout={handleGenerateCutout}
            onReviewCutout={handleCutoutReview}
            onUpdate={handleGarmentUpdate}
            onView={() => setViewingGarmentId(garment.id)}
          />
        ))}
      </div>

      {viewingGarmentId && (
        <GarmentViewer
          garment={garments.find((g) => g.id === viewingGarmentId)!}
          onClose={() => setViewingGarmentId(null)}
          isSaving={activeGarment === viewingGarmentId}
          isCutoutSaving={activeCutout === viewingGarmentId || garments.find((g) => g.id === viewingGarmentId)?.cutouts.some((asset) => asset.id === activeCutout) || false}
          onUpdate={handleGarmentUpdate}
          onGenerateCutout={handleGenerateCutout}
          onReviewCutout={handleCutoutReview}
        />
      )}

      <DuplicateReviewQueue
        isSaving={activeDuplicateReview}
        onDecide={handleDuplicateDecision}
        reviews={pendingDuplicateReviews}
      />
    </section>
  );
}

function ImportProgress({ job }: { job: ImportJob }) {
  return (
    <section className="import-progress" aria-label="Import progress">
      <div>
        <p className="eyebrow">Import {job.id.slice(0, 8)}</p>
        <strong>{humanize(job.status)} · {job.progress}%</strong>
      </div>
      <ol>
        {importStages.map((stage) => (
          <li className={job.stages.includes(stage) ? "stage-complete" : ""} key={stage}>
            {humanize(stage)}
          </li>
        ))}
      </ol>
      {job.error_message ? <p className="inline-warning">{job.error_message}</p> : null}
    </section>
  );
}

function CandidateCard({
  candidate,
  isSaving,
  onReview,
}: {
  candidate: Candidate;
  isSaving: boolean;
  onReview: (candidateId: string, review: CandidateReview) => Promise<void>;
}) {
  const [name, setName] = useState(candidate.attributes.name_suggestion ?? "Unnamed wardrobe item");
  const [category, setCategory] = useState(candidate.attributes.category ?? "top");
  const [colors, setColors] = useState((candidate.attributes.colors ?? []).join(", "));
  const [tags, setTags] = useState((candidate.attributes.tags ?? []).join(", "));
  const pending = candidate.status === "awaiting_review";
  const details = candidate.unresolved_details.length > 0 ? candidate.unresolved_details : ["No unresolved details recorded."];

  const reviewPayload = (): Omit<CandidateReview, "action"> => ({
    name: name.trim(),
    category: category.trim(),
    colors: splitList(colors),
    tags: splitList(tags),
  });

  return (
    <article className="candidate-card">
      <SourceImage alt={`Source crop for ${name}`} src={candidate.source_crop_url} />
      <div className="card-body">
        <div className="card-meta">
          <span className={statusClass(candidate.status)}>{candidateLabel(candidate.status)}</span>
          <span>{Math.round(candidate.confidence * 100)}% proposal confidence</span>
        </div>
        <h4>{name}</h4>
        <p className="source-disclosure">This is the original source crop, not a reconstructed cutout.</p>

        {pending ? (
          <>
            <div className="review-fields">
              <label>
                Name
                <input onChange={(event) => setName(event.target.value)} value={name} />
              </label>
              <label>
                Category
                <input onChange={(event) => setCategory(event.target.value)} value={category} />
              </label>
              <label>
                Colors
                <input onChange={(event) => setColors(event.target.value)} value={colors} />
              </label>
              <label>
                Tags
                <input onChange={(event) => setTags(event.target.value)} placeholder="work, linen" value={tags} />
              </label>
            </div>
            <div className="review-actions">
              <button disabled={isSaving} onClick={() => void onReview(candidate.id, { action: "edit", ...reviewPayload() })} type="button">
                Save edits
              </button>
              <button className="approve-button" disabled={isSaving} onClick={() => void onReview(candidate.id, { action: "approve", ...reviewPayload() })} type="button">
                Approve to closet
              </button>
              <button disabled={isSaving} onClick={() => void onReview(candidate.id, { action: "hold" })} type="button">
                Need better photo
              </button>
              <button className="quiet-danger" disabled={isSaving} onClick={() => void onReview(candidate.id, { action: "reject" })} type="button">
                Reject
              </button>
            </div>
          </>
        ) : null}

        <details className="review-notes">
          <summary>Review details</summary>
          <p><strong>Material:</strong> {String(candidate.attributes.apparent_material ?? "needs review")}</p>
          <p><strong>Pattern:</strong> {String(candidate.attributes.pattern ?? "needs review")}</p>
          <ul>{details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
          {candidate.reviewer_notes ? <p><strong>Decision:</strong> {candidate.reviewer_notes}</p> : null}
        </details>
      </div>
    </article>
  );
}

function GarmentCard({
  garment,
  isSaving,
  isCutoutSaving,
  onGenerateCutout,
  onReviewCutout,
  onUpdate,
  onView,
}: {
  garment: Garment;
  isSaving: boolean;
  isCutoutSaving: boolean;
  onGenerateCutout: (garmentId: string) => Promise<void>;
  onReviewCutout: (garmentId: string, assetId: string, action: "approve" | "reject") => Promise<void>;
  onUpdate: (garmentId: string, update: GarmentUpdate) => Promise<void>;
  onView: () => void;
}) {
  const latestCutout = garment.cutouts[0] ?? null;
  const hasApprovedCutout = garment.cutouts.some((asset) => asset.qa_status === "approved");

  return (
    <article className="garment-card">
      <button className="cutout-image" onClick={onView} type="button">
        {latestCutout?.asset_url && latestCutout.qa_status !== "failed" ? (
          <img alt={`Source-linked cutout candidate for ${garment.name}`} src={latestCutout.asset_url} />
        ) : garment.source_crop_url ? (
          <img alt={`Approved source crop for ${garment.name}`} src={garment.source_crop_url} />
        ) : (
          <span>Source crop unavailable</span>
        )}
      </button>
      <div className="card-body">
        <div className="card-meta">
          <span className="evidence-badge">{evidenceLabel(garment.evidence_status)}</span>
          <span>{garment.category}</span>
        </div>
        <h4>{garment.name}</h4>
        <p className="tag-line">{garment.colors.join(" · ") || "Color under review"}{garment.tags.length ? ` · ${garment.tags.join(" · ")}` : ""}</p>
      </div>
    </article>
  );
}

function GarmentViewer({
  garment,
  onClose,
  isSaving,
  isCutoutSaving,
  onGenerateCutout,
  onReviewCutout,
  onUpdate,
}: {
  garment: Garment;
  onClose: () => void;
  isSaving: boolean;
  isCutoutSaving: boolean;
  onGenerateCutout: (garmentId: string) => Promise<void>;
  onReviewCutout: (garmentId: string, assetId: string, action: "approve" | "reject") => Promise<void>;
  onUpdate: (garmentId: string, update: GarmentUpdate) => Promise<void>;
}) {
  const [name, setName] = useState(garment.name);
  const [category, setCategory] = useState(garment.category);
  const [tags, setTags] = useState(garment.tags.join(", "));
  const [price, setPrice] = useState(garment.price?.toString() ?? "");
  const latestCutout = garment.cutouts[0] ?? null;
  const hasApprovedCutout = garment.cutouts.some((asset) => asset.qa_status === "approved");

  return (
    <div className="viewer-overlay" onClick={onClose}>
      <div className="viewer-entry">
        <div className="viewer" onClick={(e) => e.stopPropagation()}>
          <button className="viewer-close" onClick={onClose} aria-label="Close viewer" type="button">×</button>
          
          <div className="viewer-header">
            <h3>{garment.name}</h3>
            <p className="tag-line">{garment.colors.join(" · ")}</p>
          </div>

          <div className="viewer-image">
            {latestCutout?.asset_url && latestCutout.qa_status !== "failed" ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt={`Cutout for ${garment.name}`} src={latestCutout.asset_url} />
            ) : garment.source_crop_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt={`Source crop for ${garment.name}`} src={garment.source_crop_url} />
            ) : null}
          </div>

          <p className="source-disclosure">
            {garment.evidence_status === "verified_source_backed"
              ? "Approved from source evidence. Metadata edits do not change the photo or provenance."
              : garment.evidence_status === "ai_reconstructed"
                ? "AI-reconstructed asset — human review is still required."
                : "This item needs a clearer photo before it can be trusted as inventory."}
          </p>

          <CutoutReviewPanel
            garment={garment}
            hasApprovedCutout={hasApprovedCutout}
            isSaving={isCutoutSaving}
            latestCutout={latestCutout}
            onGenerate={onGenerateCutout}
            onReview={onReviewCutout}
          />
          
          <div className="metadata-editor">
            <h4>Edit closet metadata</h4>
            <div className="review-fields">
              <label>Name<input onChange={(event) => setName(event.target.value)} value={name} /></label>
              <label>Category<input onChange={(event) => setCategory(event.target.value)} value={category} /></label>
              <label>Tags<input onChange={(event) => setTags(event.target.value)} value={tags} /></label>
              <label>Price<input inputMode="decimal" onChange={(event) => setPrice(event.target.value)} placeholder="Optional" value={price} /></label>
            </div>
            <div className="review-actions">
              <button
                className="approve-button"
                disabled={isSaving}
                onClick={() => void onUpdate(garment.id, {
                  name: name.trim(),
                  category: category.trim(),
                  tags: splitList(tags),
                  ...(price.trim() ? { price: Number(price) } : {}),
                })}
                type="button"
              >
                Save metadata
              </button>
              <button className="quiet-danger" disabled={isSaving} onClick={() => void onUpdate(garment.id, { archive: true })} type="button">
                Archive
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CutoutReviewPanel({
  garment,
  hasApprovedCutout,
  isSaving,
  latestCutout,
  onGenerate,
  onReview,
}: {
  garment: Garment;
  hasApprovedCutout: boolean;
  isSaving: boolean;
  latestCutout: Garment["cutouts"][number] | null;
  onGenerate: (garmentId: string) => Promise<void>;
  onReview: (garmentId: string, assetId: string, action: "approve" | "reject") => Promise<void>;
}) {
  if (latestCutout?.qa_status === "awaiting_review") {
    return (
      <section className="cutout-review" aria-label={`Review cutout for ${garment.name}`}>
        <strong>Cutout QA passed — human review required</strong>
        <p>Transparent-background candidate derived from the preserved source crop. Approving it does not alter the source.</p>
        {latestCutout.qa_warnings.length > 0 ? <p className="cutout-warning">{latestCutout.qa_warnings.join(" ")}</p> : null}
        <div className="review-actions">
          <button
            className="approve-button"
            disabled={isSaving}
            onClick={() => void onReview(garment.id, latestCutout.id, "approve")}
            type="button"
          >
            Approve cutout
          </button>
          <button
            className="quiet-danger"
            disabled={isSaving}
            onClick={() => void onReview(garment.id, latestCutout.id, "reject")}
            type="button"
          >
            Reject cutout
          </button>
        </div>
      </section>
    );
  }

  if (hasApprovedCutout) {
    return (
      <section className="cutout-review cutout-approved" aria-label={`Approved cutout for ${garment.name}`}>
        <strong>Approved source-backed cutout</strong>
        <p>Alpha QA passed and you approved this derivative. The original crop remains the primary evidence.</p>
      </section>
    );
  }

  const failed = latestCutout?.qa_status === "failed" || latestCutout?.qa_status === "rejected";
  return (
    <section className={failed ? "cutout-review cutout-held" : "cutout-review"} aria-label={`Cutout QA for ${garment.name}`}>
      <strong>{failed ? "Needs a better photo" : "No cutout has been approved"}</strong>
      <p>
        {failed
          ? "The source failed conservative alpha QA, so Fit Check did not call it a cutout. Use an isolated or clean-background photo."
          : "Run deterministic chroma and alpha QA on this approved source crop. It never uses a generative provider in mock mode."}
      </p>
      {latestCutout?.qa_warnings.length ? <p className="cutout-warning">{latestCutout.qa_warnings.join(" ")}</p> : null}
      <div className="review-actions">
        <button
          disabled={isSaving}
          onClick={() => void onGenerate(garment.id)}
          type="button"
        >
          {isSaving ? "Running alpha QA…" : failed ? "Retry with source crop" : "Run alpha QA"}
        </button>
      </div>
    </section>
  );
}

function DuplicateReviewQueue({
  isSaving,
  onDecide,
  reviews,
}: {
  isSaving: string | null;
  onDecide: (reviewId: string, action: "keep_separate" | "mark_likely_duplicate") => Promise<void>;
  reviews: DuplicateReview[];
}) {
  return (
    <section className="duplicate-queue" aria-labelledby="duplicate-review-heading">
      <div className="closet-heading">
        <div>
          <p className="eyebrow">Conservative duplicate review</p>
          <h3 id="duplicate-review-heading">Similar does not mean the same.</h3>
        </div>
        <span className="duplicate-count">{reviews.length} review-only match{reviews.length === 1 ? "" : "es"}</span>
      </div>
      <p className="workbench-copy">
        Local 16×16 luminance signatures only flag closely matching, approved cutouts in the same category. Fit Check never merges, archives, or deletes either item automatically.
      </p>
      {reviews.length === 0 ? (
        <p className="empty-state">No close visual matches need your attention.</p>
      ) : (
        <div className="duplicate-grid">
          {reviews.map((review) => (
            <article className="duplicate-card" key={review.id}>
              <div className="duplicate-meta">
                <span className="review-badge">Human review required</span>
                <span>{Math.round(review.score * 100)}% visual similarity</span>
              </div>
              <div className="duplicate-pair">
                <DuplicateGarmentPreview garment={review.garment_a} />
                <DuplicateGarmentPreview garment={review.garment_b} />
              </div>
              <p className="source-disclosure">Review only: both garments stay in your closet, whatever you choose.</p>
              <div className="review-actions">
                <button
                  className="approve-button"
                  disabled={isSaving === review.id}
                  onClick={() => void onDecide(review.id, "keep_separate")}
                  type="button"
                >
                  Keep both
                </button>
                <button
                  disabled={isSaving === review.id}
                  onClick={() => void onDecide(review.id, "mark_likely_duplicate")}
                  type="button"
                >
                  Mark likely duplicate
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function DuplicateGarmentPreview({ garment }: { garment: DuplicateReview["garment_a"] }) {
  return (
    <div className="duplicate-garment-preview">
      <CutoutImage alt={`Cutout for ${garment.name}`} src={garment.cutout_url} compact />
      <strong>{garment.name}</strong>
      <span>{garment.category} · {garment.colors.join(", ") || "color under review"}</span>
    </div>
  );
}

function SourceImage({ alt, src }: { alt: string; src: string | null }) {
  return (
    <div className="source-image">
      {src ? (
        // Source crops are personal/private URLs; do not route them through a public optimizer.
        // eslint-disable-next-line @next/next/no-img-element
        <img alt={alt} src={src} />
      ) : <span>Source crop unavailable</span>}
    </div>
  );
}

function CutoutImage({ alt, compact = false, src }: { alt: string; compact?: boolean; src: string | null }) {
  return (
    <div className={compact ? "cutout-image cutout-image-compact" : "cutout-image"}>
      {src ? (
        // This private signed URL is a source-linked derivative; no public image optimization.
        // eslint-disable-next-line @next/next/no-img-element
        <img alt={alt} src={src} />
      ) : <span>Cutout unavailable</span>}
    </div>
  );
}

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function candidateLabel(status: string): string {
  if (status === "approved") return "Verified source-backed";
  if (status === "needs_better_photo") return "Needs a better photo";
  if (status === "rejected") return "Rejected";
  return "Review required";
}

function evidenceLabel(status: Garment["evidence_status"]): string {
  if (status === "ai_reconstructed") return "AI-reconstructed";
  if (status === "needs_better_photo") return "Needs better photo";
  return "Verified source-backed";
}

function statusClass(status: string): string {
  if (status === "approved") return "evidence-badge";
  if (status === "needs_better_photo") return "hold-badge";
  if (status === "rejected") return "rejected-badge";
  return "review-badge";
}
