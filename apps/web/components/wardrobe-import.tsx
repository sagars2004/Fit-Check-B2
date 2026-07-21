"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  type Candidate,
  type CandidateReview,
  type Garment,
  type GarmentUpdate,
  type ImportJob,
  createImport,
  getCandidates,
  getGarments,
  reviewCandidate,
  updateGarment,
  uploadPhotos,
} from "../lib/api";

type LoadState = "loading" | "ready" | "error";

const importStages = ["uploaded", "inventorying", "awaiting_review", "extracting", "quality_check", "complete"];

export function WardrobeImport() {
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [garments, setGarments] = useState<Garment[]>([]);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [uploading, setUploading] = useState(false);
  const [activeCandidate, setActiveCandidate] = useState<string | null>(null);
  const [activeGarment, setActiveGarment] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [candidateItems, garmentItems] = await Promise.all([getCandidates(), getGarments()]);
      setCandidates(candidateItems);
      setGarments(garmentItems);
      setLoadState("ready");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Unable to load the local wardrobe.");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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

  return (
    <section className="wardrobe-workbench" aria-labelledby="wardrobe-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Milestone 1 · import and closet</p>
          <h2 id="wardrobe-heading">Build a closet you can trust.</h2>
        </div>
        <span className="status-pill status-review">
          {loadState === "loading" ? "Loading private closet" : `${garments.length} approved item${garments.length === 1 ? "" : "s"}`}
        </span>
      </div>

      <p className="workbench-copy">
        Upload outfit photos privately, then review the preserved source crop before it enters your
        wardrobe. Fit Check never calls a guessed crop a verified cutout, and it never auto-merges
        similar clothes.
      </p>

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
      {error ? <p className="error-message" role="alert">{error}</p> : null}

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
          <h3>Approved items, with the source still visible.</h3>
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
            isSaving={activeGarment === garment.id}
            key={garment.id}
            onUpdate={handleGarmentUpdate}
          />
        ))}
      </div>
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
  onUpdate,
}: {
  garment: Garment;
  isSaving: boolean;
  onUpdate: (garmentId: string, update: GarmentUpdate) => Promise<void>;
}) {
  const [name, setName] = useState(garment.name);
  const [category, setCategory] = useState(garment.category);
  const [tags, setTags] = useState(garment.tags.join(", "));
  const [price, setPrice] = useState(garment.price?.toString() ?? "");

  return (
    <article className="garment-card">
      <SourceImage alt={`Approved source crop for ${garment.name}`} src={garment.source_crop_url} />
      <div className="card-body">
        <div className="card-meta">
          <span className="evidence-badge">{evidenceLabel(garment.evidence_status)}</span>
          <span>{garment.category}</span>
        </div>
        <h4>{garment.name}</h4>
        <p className="tag-line">{garment.colors.join(" · ") || "Color under review"}{garment.tags.length ? ` · ${garment.tags.join(" · ")}` : ""}</p>
        <p className="source-disclosure">
          {garment.evidence_status === "verified_source_backed"
            ? "Approved from source evidence. Metadata edits do not change the photo or provenance."
            : garment.evidence_status === "ai_reconstructed"
              ? "AI-reconstructed asset — human review is still required."
              : "This item needs a clearer photo before it can be trusted as inventory."}
        </p>
        <details className="metadata-editor">
          <summary>Edit closet metadata</summary>
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
            <button disabled={isSaving} onClick={() => void onUpdate(garment.id, { archive: true })} type="button">
              Archive
            </button>
          </div>
        </details>
      </div>
    </article>
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
