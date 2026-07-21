"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type ModelProfile,
  type OutfitItem,
  type OutfitPlan,
  type Provenance,
  type TryOnRender,
  deleteModelProfile,
  getModelProfiles,
  getOutfitRenders,
  getProvenance,
  renderOutfit,
  uploadReferencePhoto,
} from "../lib/api";

type RenderSourceGarment = {
  id: string;
  name: string;
  category: string;
  colors: string[];
  evidence_status: string;
  image_url: string | null;
  source_kind?: string;
};

type TryOnRenderWithSources = TryOnRender;

type PreviewSourceGarment = RenderSourceGarment;

type TryOnStudioProps = {
  outfit: OutfitPlan | null;
  onClearSelection: () => void;
};

const maxReferencePhotoSize = 15 * 1024 * 1024;
const permittedReferenceTypes = new Set(["image/jpeg", "image/png", "image/webp"]);

export function TryOnStudio({ outfit, onClearSelection }: TryOnStudioProps) {
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [hasConsent, setHasConsent] = useState(false);
  const [renders, setRenders] = useState<TryOnRenderWithSources[]>([]);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(true);
  const [isLoadingRenders, setIsLoadingRenders] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [deletingProfileId, setDeletingProfileId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [correctionHint, setCorrectionHint] = useState("");
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [isLoadingProvenance, setIsLoadingProvenance] = useState(false);

  const outfitId = outfit?.id;
  const activeOutfitIdRef = useRef<string | undefined>(outfitId);
  activeOutfitIdRef.current = outfitId;

  const refreshProfiles = useCallback(async () => {
    setIsLoadingProfiles(true);
    try {
      setProfiles(await getModelProfiles());
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Your saved reference photos could not be loaded.");
    } finally {
      setIsLoadingProfiles(false);
    }
  }, []);

  const refreshRenders = useCallback(async (selectedOutfitId: string) => {
    setIsLoadingRenders(true);
    try {
      const response = await getOutfitRenders(selectedOutfitId);
      if (activeOutfitIdRef.current === selectedOutfitId) {
        setRenders(sortRenders(response));
      }
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The selected look's previews could not be loaded.");
    } finally {
      setIsLoadingRenders(false);
    }
  }, []);

  useEffect(() => {
    void refreshProfiles();
  }, [refreshProfiles]);

  useEffect(() => {
    setRenders([]);
    setProvenance(null);
    if (outfitId) {
      void refreshRenders(outfitId);
    }
  }, [outfitId, refreshRenders]);

  const hasQueuedPreview = renders.some((render) => render.status === "preview_generating");
  useEffect(() => {
    if (!outfitId || !hasQueuedPreview) return;
    const poll = window.setInterval(() => {
      void refreshRenders(outfitId);
    }, 1_500);
    return () => window.clearInterval(poll);
  }, [hasQueuedPreview, outfitId, refreshRenders]);

  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const currentRender = renders[0] ?? null;
  const selectedOutfitSources = useMemo<PreviewSourceGarment[]>(() => {
    if (!outfit) return [];
    return outfit.items.map(outfitItemToSourceGarment);
  }, [outfit]);
  const previewSources = currentRender?.source_garments?.length
    ? currentRender.source_garments
    : selectedOutfitSources;
  const canGenerate = Boolean(
    outfit &&
      selectedProfile &&
      selectedProfile.status === "active" &&
      !isUploading &&
      !isGenerating &&
      !hasQueuedPreview &&
      currentRender?.status !== "preview_ready",
  );

  async function handleReferenceUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!referenceFile) {
      setError("Choose a JPG, PNG, or WebP reference photo first.");
      return;
    }
    if (!hasConsent) {
      setError("Confirm consent before Fit Check stores or uses a personal reference photo.");
      return;
    }
    setIsUploading(true);
    setError(null);
    setNotice(null);
    try {
      const profile = await uploadReferencePhoto(referenceFile);
      setProfiles((current) => [profile, ...current.filter((item) => item.id !== profile.id)]);
      setSelectedProfileId(profile.id);
      setReferenceFile(null);
      setHasConsent(false);
      event.currentTarget.reset();
      setNotice("Reference photo saved privately. Select it only for the look you want to preview.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "This reference photo could not be saved securely.");
    } finally {
      setIsUploading(false);
    }
  }

  function handleReferenceFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setReferenceFile(null);
      return;
    }
    if (!permittedReferenceTypes.has(file.type)) {
      setReferenceFile(null);
      setError("Reference photos must be JPG, PNG, or WebP files.");
      return;
    }
    if (file.size > maxReferencePhotoSize) {
      setReferenceFile(null);
      setError("Reference photos must be 15 MB or smaller.");
      return;
    }
    setError(null);
    setReferenceFile(file);
  }

  async function handleDeleteProfile(profileId: string) {
    setDeletingProfileId(profileId);
    setError(null);
    try {
      await deleteModelProfile(profileId);
      setProfiles((current) => current.filter((profile) => profile.id !== profileId));
      if (profileId === selectedProfileId) setSelectedProfileId(null);
      setNotice("Reference photo removed. It is separate from your wardrobe and cannot be used for future previews.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That reference photo could not be removed.");
    } finally {
      setDeletingProfileId(null);
    }
  }

  async function handleGeneratePreview() {
    if (!outfit || !selectedProfile || selectedProfile.status !== "active") {
      setError("Select one owned look and one saved, consented reference photo before requesting a preview.");
      return;
    }
    setIsGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const priorRunId = currentRender?.status === "failed" ? currentRender.run_id ?? undefined : undefined;
      const render = await renderOutfit(
        outfit.id,
        selectedProfile.id,
        priorRunId,
        correctionHint.trim() || undefined,
      );
      if (activeOutfitIdRef.current === outfit.id) {
        setProvenance(null);
        setRenders((current) => sortRenders([render, ...current.filter((item) => item.id !== render.id)]));
      }
      setCorrectionHint("");
      setNotice(
        render.status === "preview_ready"
          ? "One AI preview is ready for your selected look. Review it against the source garment cards below."
          : "Preview request received. Fit Check is validating the selected sources and tracking the private render job.",
      );
    } catch (caught: unknown) {
      const failureMessage = caught instanceof Error
        ? caught.message
        : "The preview could not be generated. Your selected outfit and reference photo are still available for retry.";
      // A failed job is durable on the server. Reload it so the user can see
      // the stable error, provenance entry point, and retry state in context.
      if (activeOutfitIdRef.current === outfit.id) await refreshRenders(outfit.id);
      setError(failureMessage);
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleOpenProvenance(render: TryOnRenderWithSources) {
    setIsLoadingProvenance(true);
    setError(null);
    try {
      setProvenance(await getProvenance(render.id, render.provenance_entity_type));
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The redacted provenance record could not be loaded.");
    } finally {
      setIsLoadingProvenance(false);
    }
  }

  return (
    <section className="tryon-studio" id="try-on-studio" aria-labelledby="try-on-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Milestone 3 · selected AI preview</p>
          <h2 id="try-on-heading">Preview one owned look on you, with the evidence in view.</h2>
        </div>
        <span className="status-pill status-review">
          {outfit ? "One selected look" : "Choose a look first"}
        </span>
      </div>
      <p className="workbench-copy">
        A preview is created only when you select one recommendation and a consented reference photo.
        It is an AI-generated visualization—not a promise about size, fit, drape, fabric, body shape,
        or unseen garment details.
      </p>

      {notice ? <p className="success-message" role="status">{notice}</p> : null}
      {error ? <p className="error-message" role="alert">{error}</p> : null}

      <div className="tryon-setup-grid">
        <SelectedOutfitCard outfit={outfit} onClearSelection={onClearSelection} sources={selectedOutfitSources} />
        <ReferencePhotoPanel
          deletingProfileId={deletingProfileId}
          hasConsent={hasConsent}
          isLoading={isLoadingProfiles}
          isUploading={isUploading}
          onConsentChange={setHasConsent}
          onDelete={handleDeleteProfile}
          onFileChange={handleReferenceFileChange}
          onSelect={setSelectedProfileId}
          onSubmit={handleReferenceUpload}
          profiles={profiles}
          referenceFile={referenceFile}
          selectedProfileId={selectedProfileId}
        />
      </div>

      {outfit ? (
        <section className="preview-request" aria-labelledby="preview-request-heading">
          <div>
            <p className="eyebrow">Step 3 · request exactly one preview</p>
            <h3 id="preview-request-heading">{outfit.title}</h3>
            <p>
              {selectedProfile
                ? "The selected reference photo is scoped to this request. Fit Check will use only the garment assets listed below."
                : "Choose one consented reference photo above to unlock this request."}
            </p>
          </div>
          <div className="preview-request-action">
            {currentRender?.status === "failed" ? (
              <label className="retry-note">
                Optional retry note
                <input
                  maxLength={500}
                  onChange={(event) => setCorrectionHint(event.target.value)}
                  placeholder="For example: keep the jacket clearly visible"
                  value={correctionHint}
                />
                <small>Sent as a constrained correction hint; the configured server-side model remains unchanged.</small>
              </label>
            ) : null}
            <button
              className="primary-button"
              disabled={!canGenerate}
              onClick={() => void handleGeneratePreview()}
              type="button"
            >
              {isGenerating
                ? "Starting preview…"
                : hasQueuedPreview
                  ? "Generating preview…"
                  : currentRender?.status === "preview_ready"
                    ? "One preview ready"
                    : currentRender?.status === "failed"
                      ? "Retry selected preview"
                      : "Generate one AI preview"}
            </button>
            <small className="preview-action-note">
              {currentRender?.status === "preview_ready"
                ? "This selected look already has one completed preview."
                : "No preview is generated until you press this button."}
            </small>
          </div>
        </section>
      ) : null}

      {outfit ? (
        <PreviewReview
          isLoading={isLoadingRenders}
          isLoadingProvenance={isLoadingProvenance}
          onOpenProvenance={handleOpenProvenance}
          outfit={outfit}
          previewSources={previewSources}
          provenance={provenance}
          render={currentRender}
          selectedProfile={selectedProfile}
        />
      ) : (
        <p className="empty-state tryon-empty-state">
          Choose <strong>Preview on me</strong> from one recommendation above. Fit Check will keep the
          specific owned garments in view before any preview can be requested.
        </p>
      )}
    </section>
  );
}

function SelectedOutfitCard({
  outfit,
  onClearSelection,
  sources,
}: {
  outfit: OutfitPlan | null;
  onClearSelection: () => void;
  sources: PreviewSourceGarment[];
}) {
  return (
    <section className="selected-look-panel" aria-labelledby="selected-look-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Step 1 · selected owned look</p>
          <h3 id="selected-look-heading">{outfit ? outfit.title : "No look selected"}</h3>
        </div>
        {outfit ? <span className="review-badge">Selected</span> : null}
      </div>
      {outfit ? (
        <>
          <p className="selected-look-reasoning">{outfit.reasoning}</p>
          <p className="source-disclosure">
            This request is locked to these approved owned garments. Selecting a preview never adds,
            replaces, or reconstructs closet inventory.
          </p>
          <SourceGarmentCards garments={sources} />
          <button className="text-button" onClick={onClearSelection} type="button">Choose a different look</button>
        </>
      ) : (
        <p className="empty-panel-copy">The weather-aware planner will provide the look selection here.</p>
      )}
    </section>
  );
}

function ReferencePhotoPanel({
  deletingProfileId,
  hasConsent,
  isLoading,
  isUploading,
  onConsentChange,
  onDelete,
  onFileChange,
  onSelect,
  onSubmit,
  profiles,
  referenceFile,
  selectedProfileId,
}: {
  deletingProfileId: string | null;
  hasConsent: boolean;
  isLoading: boolean;
  isUploading: boolean;
  onConsentChange: (value: boolean) => void;
  onDelete: (profileId: string) => Promise<void>;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSelect: (profileId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  profiles: ModelProfile[];
  referenceFile: File | null;
  selectedProfileId: string | null;
}) {
  return (
    <section className="reference-photo-panel" aria-labelledby="reference-photo-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Step 2 · consented reference photo</p>
          <h3 id="reference-photo-heading">Your photo stays separate from your closet.</h3>
        </div>
        <span className="privacy-badge">Private by default</span>
      </div>
      <p className="reference-copy">
        Upload only a photo you are authorized to use. It is stored privately and used only when you
        actively select it for an AI preview. You can remove it independently at any time.
      </p>

      <form className="reference-upload-form" onSubmit={(event) => void onSubmit(event)}>
        <label className="reference-drop-zone" htmlFor="reference-photo-upload">
          <span aria-hidden="true" className="drop-icon">↑</span>
          <span>
            <strong>{referenceFile ? referenceFile.name : "Choose a reference photo"}</strong>
            <small>JPG, PNG, or WebP · private storage · up to 15 MB</small>
          </span>
          <input
            accept="image/jpeg,image/png,image/webp"
            id="reference-photo-upload"
            onChange={onFileChange}
            type="file"
          />
        </label>
        <label className="consent-check">
          <input checked={hasConsent} onChange={(event) => onConsentChange(event.target.checked)} type="checkbox" />
          <span>
            <strong>I consent to store this personal reference photo privately and use it for the selected AI preview.</strong>
            <small>I understand the result is a visualization, not a sizing, fit, drape, or body-shape guarantee.</small>
          </span>
        </label>
        <button className="secondary-button" disabled={!referenceFile || !hasConsent || isUploading} type="submit">
          {isUploading ? "Saving private photo…" : "Save reference photo"}
        </button>
      </form>

      <fieldset className="reference-profile-list">
        <legend>Choose a saved reference photo for this preview</legend>
        {isLoading ? <p className="inline-loading" role="status">Loading private reference photos…</p> : null}
        {!isLoading && profiles.length === 0 ? (
          <p className="empty-panel-copy">No reference photo is selected. You can still organize your wardrobe without adding one.</p>
        ) : null}
        {profiles.map((profile) => {
          const isReady = profile.status === "active";
          return (
            <div className="reference-profile-card" key={profile.id}>
              <label className="reference-profile-choice">
                <input
                  checked={selectedProfileId === profile.id}
                  disabled={!isReady}
                  name="selected-reference-photo"
                  onChange={() => onSelect(profile.id)}
                  type="radio"
                  value={profile.id}
                />
                <ReferenceImage profile={profile} />
                <span className="reference-profile-info">
                  <strong>Reference photo · {formatTimestamp(profile.created_at)}</strong>
                  <small>
                    {isReady
                      ? `Consented ${formatTimestamp(profile.consented_at)} · ready for selected preview`
                      : `Consented ${formatTimestamp(profile.consented_at)} · ${humanize(profile.status)}`}
                  </small>
                </span>
              </label>
              <button
                aria-label={`Delete reference photo saved ${formatTimestamp(profile.created_at)}`}
                className="quiet-danger compact-action"
                disabled={deletingProfileId === profile.id}
                onClick={() => void onDelete(profile.id)}
                type="button"
              >
                {deletingProfileId === profile.id ? "Removing…" : "Remove"}
              </button>
            </div>
          );
        })}
      </fieldset>
    </section>
  );
}

function PreviewReview({
  isLoading,
  isLoadingProvenance,
  onOpenProvenance,
  outfit,
  previewSources,
  provenance,
  render,
  selectedProfile,
}: {
  isLoading: boolean;
  isLoadingProvenance: boolean;
  onOpenProvenance: (render: TryOnRenderWithSources) => Promise<void>;
  outfit: OutfitPlan;
  previewSources: PreviewSourceGarment[];
  provenance: Provenance | null;
  render: TryOnRenderWithSources | null;
  selectedProfile: ModelProfile | null;
}) {
  return (
    <section className="preview-review" aria-labelledby="preview-review-heading">
      <div className="review-header">
        <div>
          <p className="eyebrow">Review the selected preview</p>
          <h3 id="preview-review-heading">{render ? previewStatusLabel(render.status) : "No preview requested"}</h3>
        </div>
        {render ? <span className={previewStatusClass(render.status)}>{humanize(render.status)}</span> : null}
      </div>

      {isLoading ? <p className="inline-loading" role="status">Loading preview history for this selected look…</p> : null}
      {!isLoading && !render ? (
        <p className="empty-state">No AI preview has been requested for this look. Your garment sources remain unchanged.</p>
      ) : null}
      {render ? (
        <div className="preview-review-grid">
          <PreviewImage render={render} selectedProfile={selectedProfile} />
          <div className="preview-details">
            <p className="ai-disclosure">
              <strong>AI-generated preview.</strong> {render.disclosure || "This image is a visualization, not an exact fit or fabric simulation."}
            </p>
            {render.status === "failed" ? (
              <p className="preview-error-detail">
                <strong>{render.error_code ? `${humanize(render.error_code)}: ` : "Preview unavailable: "}</strong>
                {render.error_message ?? "Your look and consented reference photo are unchanged; retry when ready."}
              </p>
            ) : null}
            <dl className="preview-metadata">
              <div><dt>Selected look</dt><dd>{outfit.title}</dd></div>
              <div><dt>Created</dt><dd>{formatTimestamp(render.created_at)}</dd></div>
              <div><dt>Provider / model</dt><dd>{providerLabel(render)}</dd></div>
              <div><dt>Run</dt><dd>{render.run_id ?? "Awaiting orchestration"}</dd></div>
              {render.parent_run_id ? <div><dt>Retry parent</dt><dd>{render.parent_run_id}</dd></div> : null}
            </dl>
            <button
              className="secondary-button"
              disabled={isLoadingProvenance}
              onClick={() => void onOpenProvenance(render)}
              type="button"
            >
              {isLoadingProvenance ? "Loading provenance…" : "How this was made"}
            </button>
          </div>
        </div>
      ) : null}
      {render ? <PreviewProgress status={render.status} /> : null}

      <section className="preview-source-section" aria-labelledby="preview-sources-heading">
        <div>
          <p className="eyebrow">Exact selected garment sources</p>
          <h4 id="preview-sources-heading">These owned items are the preview input.</h4>
        </div>
        <p className="source-disclosure">Source evidence remains visible so an AI visualization is never mistaken for verified inventory photography.</p>
        <SourceGarmentCards garments={previewSources} />
      </section>

      {provenance && render ? <ProvenanceDrawer manifest={provenance.manifest} render={render} /> : null}
    </section>
  );
}

function PreviewProgress({ status }: { status: string }) {
  const ready = status === "preview_ready";
  const failed = status === "failed";
  return (
    <ol className="preview-progress" aria-label="Selected preview progress">
      <li className="stage-complete">Selected look and consent confirmed</li>
      <li className={ready || failed ? "stage-complete" : "stage-active"}>
        {failed ? "Private render job ended with an actionable error" : ready ? "Private render job completed" : "Validating sources and generating preview"}
      </li>
      <li className={ready ? "stage-complete" : failed ? "stage-failed" : ""}>
        {ready ? "Ready for your review" : failed ? "Retry remains available" : "Preview review pending"}
      </li>
    </ol>
  );
}

function PreviewImage({
  render,
  selectedProfile,
}: {
  render: TryOnRenderWithSources;
  selectedProfile: ModelProfile | null;
}) {
  if (render.status === "preview_ready" && render.render_url) {
    return (
      <figure className="preview-image-frame">
        {/* Preview media is an owner-scoped URL; do not pass it to a public optimizer. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt="AI-generated preview of the selected outfit" src={render.render_url} />
        <figcaption>AI-generated visualization · review against source garment evidence</figcaption>
      </figure>
    );
  }
  return (
    <div className="preview-image-frame preview-placeholder" role="status">
      <span aria-hidden="true">✦</span>
      <strong>{render.status === "failed" ? "Preview needs attention" : "Preparing selected preview"}</strong>
      <small>
        {render.status === "failed"
          ? "No image was accepted or substituted. Your selected sources remain available for retry."
          : selectedProfile
            ? "Reference consent confirmed · private render job in progress"
            : "Waiting for the selected reference photo"}
      </small>
    </div>
  );
}

function SourceGarmentCards({ garments }: { garments: PreviewSourceGarment[] }) {
  return (
    <div className="tryon-garment-grid">
      {garments.map((garment) => (
        <article className="tryon-garment-card" key={garment.id}>
          <SourceGarmentImage garment={garment} />
          <div>
            <span className={evidenceClass(garment.evidence_status)}>{evidenceLabel(garment.evidence_status)}</span>
            <strong>{garment.name}</strong>
            <small>{humanize(garment.category)} · {garment.colors.join(" · ") || "Color under review"}</small>
            {garment.source_kind ? <small>{sourceKindLabel(garment.source_kind)}</small> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function SourceGarmentImage({ garment }: { garment: PreviewSourceGarment }) {
  if (garment.image_url) {
    return (
      <div className="tryon-source-image">
        {/* Source thumbnails use private, owner-scoped URLs. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt={`Source garment: ${garment.name}`} src={garment.image_url} />
      </div>
    );
  }
  return <div className="tryon-source-image source-image-unavailable"><span aria-hidden="true">✦</span><small>Private source</small></div>;
}

function ReferenceImage({ profile }: { profile: ModelProfile }) {
  if (profile.source_image_url) {
    return (
      <span className="reference-profile-image">
        {/* The personal reference image stays on its scoped owner URL. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt="Saved personal reference photo" src={profile.source_image_url} />
      </span>
    );
  }
  return <span aria-hidden="true" className="reference-profile-image reference-profile-fallback">✦</span>;
}

function ProvenanceDrawer({
  manifest,
  render,
}: {
  manifest: Record<string, unknown>;
  render: TryOnRenderWithSources;
}) {
  const safeManifest = redactSensitiveManifest(manifest);
  return (
    <section className="tryon-provenance" aria-labelledby="tryon-provenance-heading">
      <div>
        <p className="eyebrow">Private provenance record</p>
        <h4 id="tryon-provenance-heading">How this selected preview was made</h4>
      </div>
      <dl className="provenance-facts">
        <div><dt>Source garment IDs</dt><dd>{render.source_garment_ids.join(", ") || "Recorded in manifest"}</dd></div>
        <div><dt>Provider / model</dt><dd>{providerLabel(render)}</dd></div>
        <div><dt>Run / parent run</dt><dd>{render.run_id ?? "pending"}{render.parent_run_id ? ` / ${render.parent_run_id}` : ""}</dd></div>
        <div><dt>Output SHA-256</dt><dd>{render.sha256 ?? "pending"}</dd></div>
      </dl>
      <details>
        <summary>Developer verification details (redacted)</summary>
        <p>Raw signed URLs, personal-image locations, and prompt text are intentionally omitted here.</p>
        <pre>{JSON.stringify(safeManifest, null, 2)}</pre>
      </details>
    </section>
  );
}

function outfitItemToSourceGarment(item: OutfitItem): PreviewSourceGarment {
  return {
    id: item.garment_id,
    name: item.name,
    category: item.category,
    colors: item.colors,
    evidence_status: item.evidence_status,
    image_url: item.image_url,
    source_kind: "selected_outfit_item",
  };
}

function sortRenders(renders: TryOnRenderWithSources[]): TryOnRenderWithSources[] {
  return [...renders].sort((left, right) => right.created_at.localeCompare(left.created_at));
}

function previewStatusLabel(status: string): string {
  if (status === "preview_ready") return "One preview ready to review";
  if (status === "failed") return "Preview did not complete";
  return "Preparing your selected preview";
}

function previewStatusClass(status: string): string {
  if (status === "preview_ready") return "evidence-badge";
  if (status === "failed") return "rejected-badge";
  return "hold-badge";
}

function providerLabel(render: TryOnRender): string {
  if (!render.provider && !render.model) return "Pending configured provider";
  return [render.provider, render.model].filter(Boolean).join(" · ");
}

function evidenceLabel(status: string): string {
  if (status === "verified_source_backed") return "Verified source-backed";
  if (status === "ai_reconstructed") return "AI-reconstructed";
  if (status === "needs_better_photo") return "Needs better photo";
  return humanize(status);
}

function evidenceClass(status: string): string {
  if (status === "needs_better_photo") return "hold-badge";
  if (status === "ai_reconstructed") return "review-badge";
  return "evidence-badge";
}

function sourceKindLabel(sourceKind: string): string {
  if (sourceKind === "approved_cutout") return "Approved cutout input";
  if (sourceKind === "source_crop_fallback") return "Source crop fallback";
  if (sourceKind === "selected_outfit_item") return "Selected outfit item";
  return humanize(sourceKind);
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function redactSensitiveManifest(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactSensitiveManifest);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !isSensitiveProvenanceKey(key))
      .map(([key, nested]) => [key, redactSensitiveManifest(nested)]),
  );
}

function isSensitiveProvenanceKey(key: string): boolean {
  const normalized = key.toLowerCase();
  if (normalized === "manifest_key" || normalized === "manifest_uri") return false;
  return ["prompt", "url", "token", "secret", "authorization", "api_key", "reference_image"].some((fragment) => normalized.includes(fragment));
}
