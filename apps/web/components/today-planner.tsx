"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { handleImgError } from "../lib/constants";


import {
  type Garment,
  type OutfitItem,
  type OutfitPlan,
  type OutfitRecommendation,
  createCustomOutfit,
  getGarments,
  recordOutfitWear,
  recommendOutfits,
  saveOutfit,
} from "../lib/api";


type ActiveAction = { outfitId: string; kind: "save" | "wear" | "undo" } | null;

type TodayPlannerProps = {
  onPreviewOutfit?: (outfit: OutfitPlan) => void;
  selectedPreviewOutfitId?: string | null;
};

export function TodayPlanner({ onPreviewOutfit, selectedPreviewOutfitId = null }: TodayPlannerProps) {
  const [location, setLocation] = useState("");
  const [forecastDate, setForecastDate] = useState(todayIso());
  const [occasion, setOccasion] = useState("");
  const [utilizationMode, setUtilizationMode] = useState(false);
  const [recommendation, setRecommendation] = useState<OutfitRecommendation | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [activeAction, setActiveAction] = useState<ActiveAction>(null);
  const [viewingOutfitId, setViewingOutfitId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [allGarments, setAllGarments] = useState<Garment[]>([]);
  const [selectedTopId, setSelectedTopId] = useState<string>("");
  const [selectedBottomId, setSelectedBottomId] = useState<string>("");
  const [isCreatingCustom, setIsCreatingCustom] = useState(false);

  useEffect(() => {
    async function loadGarments() {
      try {
        const items = await getGarments();
        setAllGarments(items.filter((g) => g.status === "approved"));
      } catch {
        // Safe ignore
      }
    }
    void loadGarments();
  }, []);

  const tops = useMemo(() => {
    const matched = allGarments.filter((g) => {
      const cat = g.category.toLowerCase();
      return (
        cat.includes("top") ||
        cat.includes("shirt") ||
        cat.includes("jacket") ||
        cat.includes("outerwear") ||
        cat.includes("sweater") ||
        cat.includes("hoodie") ||
        cat.includes("coat") ||
        cat.includes("blazer") ||
        cat.includes("t-shirt")
      );
    });
    return matched.length > 0 ? matched : allGarments;
  }, [allGarments]);

  const bottoms = useMemo(() => {
    const matched = allGarments.filter((g) => {
      const cat = g.category.toLowerCase();
      return (
        cat.includes("bottom") ||
        cat.includes("pants") ||
        cat.includes("jeans") ||
        cat.includes("shorts") ||
        cat.includes("skirt") ||
        cat.includes("trouser") ||
        cat.includes("legging")
      );
    });
    return matched.length > 0 ? matched : allGarments;
  }, [allGarments]);

  const selectedTopGarment = allGarments.find((g) => g.id === selectedTopId);
  const selectedBottomGarment = allGarments.find((g) => g.id === selectedBottomId);

  async function handleCreateCustom() {
    const ids: string[] = [];
    if (selectedTopId) ids.push(selectedTopId);
    if (selectedBottomId) ids.push(selectedBottomId);
    if (ids.length === 0) return;

    setIsCreatingCustom(true);
    setError(null);
    setNotice(null);
    try {
      const customOutfit = await createCustomOutfit(ids);
      setNotice("Custom outfit created! Sent to Try-On Studio below.");
      if (onPreviewOutfit) {
        onPreviewOutfit(customOutfit);
      }
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Could not create custom outfit combination.");
    } finally {
      setIsCreatingCustom(false);
    }
  }


  useEffect(() => {
    if (viewingOutfitId) {
      document.body.classList.add("viewer-open");
    } else {
      document.body.classList.remove("viewer-open");
    }
    return () => document.body.classList.remove("viewer-open");
  }, [viewingOutfitId]);

  async function handlePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsPlanning(true);
    setError(null);
    setNotice(null);
    try {
      const next = await recommendOutfits({
        location: location.trim() || undefined,
        forecast_date: forecastDate,
        occasion: occasion.trim() || "Everyday",
        utilization_mode: utilizationMode,
      });
      setRecommendation(next);
      setNotice(
        `${next.options.length} outfit${next.options.length === 1 ? "" : "s"} planned for your day.`,
      );
    } catch (caught: unknown) {
      setRecommendation(null);
      setError(caught instanceof Error ? caught.message : "Fit Check could not plan a look yet.");
    } finally {
      setIsPlanning(false);
    }
  }

  async function handleSave(outfitId: string) {
    setActiveAction({ outfitId, kind: "save" });
    setError(null);
    try {
      const saved = await saveOutfit(outfitId);
      replaceOption(saved);
      setNotice("Look saved to your collection.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "That look could not be saved.");
    } finally {
      setActiveAction(null);
    }
  }

  async function handleWear(outfit: OutfitPlan, action: "wear" | "undo") {
    setActiveAction({ outfitId: outfit.id, kind: action });
    setError(null);
    try {
      const result = await recordOutfitWear(outfit.id, action, forecastDate);
      replaceOption({ ...outfit, status: result.outfit_status, items: outfit.items.map((item) => ({
        ...item,
        wear_count: result.garment_wear_counts[item.garment_id] ?? item.wear_count,
        cost_per_wear: result.garment_cost_per_wear[item.garment_id] ?? item.cost_per_wear,
      })) });
      setNotice(
        action === "wear"
          ? "Wear logged successfully."
          : "Wear log restored.",
      );
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The wear log could not be updated.");
    } finally {
      setActiveAction(null);
    }
  }

  function replaceOption(next: OutfitPlan) {
    setRecommendation((current) => current
      ? { ...current, options: current.options.map((option) => option.id === next.id ? next : option) }
      : current);
  }

  return (
    <section
      aria-busy={isPlanning}
      aria-labelledby="today-heading"
      className="today-planner bento-grid"
      id="today"
      tabIndex={-1}
    >
      <div className="bento-box bento-col-12">
        <div className="section-heading">
        <div>
          <p className="eyebrow">Milestone 2 · today</p>
          <h2 id="today-heading">A useful answer for the day you actually have.</h2>
        </div>
        <span className="status-pill status-ready">Owned-only planner</span>
      </div>
      <p className="workbench-copy">
        Smart recommendations tailored to your local weather, occasion, and wardrobe.
      </p>
      </div>

      <div className="bento-box bento-col-12">
        <div className="panel-heading">
          <h3>Plan a look</h3>
        </div>
        <form className="today-context today-context-full" onSubmit={(event) => void handlePlan(event)}>
          <div className="today-context-fields">
            <label>
              Location
              <input onChange={(event) => setLocation(event.target.value)} placeholder="e.g. New York, NY" value={location} />
            </label>
            <label>
              Date
              <input onChange={(event) => setForecastDate(event.target.value)} type="date" value={forecastDate} />
            </label>
            <label className="occasion-field">
              Occasion or context
              <input
                onChange={(event) => setOccasion(event.target.value)}
                placeholder="e.g. Rainy commute, dinner after work"
                value={occasion}
              />
            </label>
          </div>
          <div className="today-context-actions">
            <label className="utilization-toggle">
              <input
                checked={utilizationMode}
                onChange={(event) => setUtilizationMode(event.target.checked)}
                type="checkbox"
              />
              <span>
                <strong>Utilization mode</strong>
                <small>Prioritize less-worn items.</small>
              </span>
            </label>
            <button className="primary-button" disabled={isPlanning} type="submit">
              {isPlanning ? "Planning owned looks…" : "Plan three looks"}
            </button>
          </div>
        </form>
      </div>

      {(notice || error) ? (
        <div className="bento-col-12" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {notice ? <p className="success-message" role="status" style={{ marginBottom: 0 }}>{notice}</p> : null}
          {error ? <p className="error-message" role="alert" style={{ marginBottom: 0 }}>{error}</p> : null}
        </div>
      ) : null}

      {recommendation ? (
        <div className="bento-box bento-col-12">
          <section className="forecast-card" aria-label="Forecast context" style={{ border: 'none', margin: 0, padding: 0 }}>
            <div>
              <p className="eyebrow">Forecast</p>
              <h3>{recommendation.weather.location}</h3>
              <p>{formatDate(recommendation.weather.forecast_date)} · {recommendation.weather.condition}</p>
            </div>
            <dl>
              <div><dt>Temperature</dt><dd>{Math.round(recommendation.weather.low_f)}–{Math.round(recommendation.weather.high_f)}°F</dd></div>
              <div><dt>Rain</dt><dd>{recommendation.weather.precipitation_probability}% · {recommendation.weather.precipitation_inch} in</dd></div>
              <div><dt>Wind</dt><dd>{Math.round(recommendation.weather.wind_mph)} mph</dd></div>
            </dl>
            {recommendation.weather.advisory ? <p className="forecast-advisory">{recommendation.weather.advisory}</p> : null}
          </section>

          {recommendation.warnings.length > 0 ? (
            <section className="planner-warnings" aria-label="Wardrobe coverage notes" style={{ marginTop: '16px' }}>
              <strong>Wardrobe coverage note</strong>
              <ul>{recommendation.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {recommendation ? (
        <div className="bento-box bento-col-12">
          <div className="recommendation-heading">
            <div>
              <p className="eyebrow">Three valid options</p>
              <h3>For {recommendation.occasion}</h3>
            </div>
            <span>Outfit Breakdown</span>
          </div>
          <div className="outfit-grid">
            {recommendation.options.map((outfit, index) => (
              <OutfitCard
                key={outfit.id}
                outfit={outfit}
                rank={index + 1}
                isSelected={selectedPreviewOutfitId === outfit.id}
                onPreview={onPreviewOutfit}
                onView={() => setViewingOutfitId(outfit.id)}
              />
            ))}
          </div>

          {viewingOutfitId && (
            <OutfitViewer
              activeAction={activeAction}
              onClose={() => setViewingOutfitId(null)}
              onPreview={onPreviewOutfit}
              onSave={handleSave}
              onWear={handleWear}
              outfit={recommendation.options.find((o) => o.id === viewingOutfitId)!}
              previewSelected={selectedPreviewOutfitId === viewingOutfitId}
            />
          )}
        </div>
      ) : null}

      {allGarments.length > 0 ? (
        <div className="bento-box bento-col-12" style={{ marginTop: '16px' }}>
          <div className="recommendation-heading">
            <div>
              <p className="eyebrow">Mix & Match</p>
              <h3>Build a Custom Combination</h3>
            </div>
            <span>Manual Top & Bottom Selection</span>
          </div>

          <div className="custom-builder-grid">
            <div className="custom-builder-field">
              <label htmlFor="custom-top-select">
                <strong>Select Top</strong>
                <small>Tops, shirts, jackets, or sweaters</small>
              </label>
              <div className="custom-select-wrapper">
                <select
                  id="custom-top-select"
                  value={selectedTopId}
                  onChange={(e) => setSelectedTopId(e.target.value)}
                >
                  <option value="">-- Choose a Top --</option>
                  {tops.map((top) => (
                    <option key={top.id} value={top.id}>
                      {top.name} ({humanize(top.category)})
                    </option>
                  ))}
                </select>
              </div>
              {selectedTopGarment ? (
                <div className="custom-item-mini-card">
                  {selectedTopGarment.source_crop_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selectedTopGarment.source_crop_url} alt={selectedTopGarment.name} className="mini-garment-thumb" onError={handleImgError} />
                  ) : (
                    <span className="mini-thumb-fallback">👕</span>
                  )}
                  <div>
                    <strong>{selectedTopGarment.name}</strong>
                    <small>{humanize(selectedTopGarment.category)} · {selectedTopGarment.colors.join(", ") || "Approved"}</small>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="custom-builder-field">
              <label htmlFor="custom-bottom-select">
                <strong>Select Bottom</strong>
                <small>Pants, shorts, jeans, or skirts</small>
              </label>
              <div className="custom-select-wrapper">
                <select
                  id="custom-bottom-select"
                  value={selectedBottomId}
                  onChange={(e) => setSelectedBottomId(e.target.value)}
                >
                  <option value="">-- Choose a Bottom --</option>
                  {bottoms.map((bottom) => (
                    <option key={bottom.id} value={bottom.id}>
                      {bottom.name} ({humanize(bottom.category)})
                    </option>
                  ))}
                </select>
              </div>
              {selectedBottomGarment ? (
                <div className="custom-item-mini-card">
                  {selectedBottomGarment.source_crop_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selectedBottomGarment.source_crop_url} alt={selectedBottomGarment.name} className="mini-garment-thumb" onError={handleImgError} />
                  ) : (
                    <span className="mini-thumb-fallback">👖</span>
                  )}

                  <div>
                    <strong>{selectedBottomGarment.name}</strong>
                    <small>{humanize(selectedBottomGarment.category)} · {selectedBottomGarment.colors.join(", ") || "Approved"}</small>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="custom-builder-action">
              <button
                className="primary-button"
                disabled={isCreatingCustom || (!selectedTopId && !selectedBottomId)}
                onClick={() => void handleCreateCustom()}
                type="button"
                style={{ width: '100%', height: '48px' }}
              >
                {isCreatingCustom ? "Creating Custom Look…" : "Preview Custom Pair on me →"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}


function OutfitCard({
  outfit,
  rank,
  onView,
  onPreview,
  isSelected = false,
}: {
  outfit: OutfitPlan;
  rank: number;
  onView: () => void;
  onPreview?: (outfit: OutfitPlan) => void;
  isSelected?: boolean;
}) {
  return (
    <article className={`outfit-card ${isSelected ? "outfit-card-selected" : ""}`} onClick={onView}>
      <div className="outfit-card-meta">
        <span className="review-badge">Option {rank}</span>
        <span>{Math.round(outfit.score)} suitability</span>
      </div>
      <h4>{outfit.title}</h4>
      <p className="outfit-reasoning">{outfit.reasoning}</p>

      <div className="outfit-card-actions" style={{ marginTop: "auto", paddingTop: "12px", display: "flex", gap: "8px", alignItems: "center" }}>
        {onPreview ? (
          <button
            className={isSelected ? "preview-button preview-button-selected" : "primary-button"}
            onClick={(event) => {
              event.stopPropagation();
              onPreview(outfit);
            }}
            type="button"
            style={{ fontSize: "0.8rem", padding: "8px 14px" }}
          >
            {isSelected ? "Selected for preview ✓" : "Preview on me →"}
          </button>
        ) : null}
        <button
          className="secondary-button"
          onClick={(event) => {
            event.stopPropagation();
            onView();
          }}
          type="button"
          style={{ fontSize: "0.8rem", padding: "8px 12px" }}
        >
          Details
        </button>
      </div>
    </article>
  );
}


function OutfitViewer({
  activeAction,
  onClose,
  onPreview,
  onSave,
  onWear,
  outfit,
  previewSelected,
}: {
  activeAction: ActiveAction;
  onClose: () => void;
  onPreview?: (outfit: OutfitPlan) => void;
  onSave: (outfitId: string) => Promise<void>;
  onWear: (outfit: OutfitPlan, action: "wear" | "undo") => Promise<void>;
  outfit: OutfitPlan;
  previewSelected: boolean;
}) {
  const saving = activeAction?.outfitId === outfit.id;

  return (
    <div className="viewer-overlay" onClick={onClose}>
      <div className="viewer-entry">
        <div className="viewer" onClick={(e) => e.stopPropagation()}>
          <button className="viewer-close" onClick={onClose} aria-label="Close viewer" type="button">×</button>
          
          <div className="viewer-header">
            <h3>{outfit.title}</h3>
            <p className="outfit-reasoning">{outfit.reasoning}</p>
          </div>

          <div className="outfit-items" aria-label={`Garments in ${outfit.title}`}>
            {outfit.items.map((item) => <OutfitItemTile item={item} key={`${outfit.id}-${item.garment_id}`} />)}
          </div>

          <p className="outfit-disclosure">Garments from your approved wardrobe.</p>
          
          <div className="review-actions" style={{ marginTop: "24px" }}>
            <button disabled={saving || outfit.status === "saved" || outfit.status === "worn"} onClick={() => void onSave(outfit.id)} type="button">
              {saving && activeAction?.kind === "save" ? "Saving…" : outfit.status === "saved" || outfit.status === "worn" ? "Saved" : "Save"}
            </button>
            {outfit.status === "worn" ? (
              <button disabled={saving} onClick={() => void onWear(outfit, "undo")} type="button">
                {saving && activeAction?.kind === "undo" ? "Reversing…" : "Undo wear"}
              </button>
            ) : (
              <button className="approve-button" disabled={saving} onClick={() => void onWear(outfit, "wear")} type="button">
                {saving && activeAction?.kind === "wear" ? "Logging…" : "Wear it"}
              </button>
            )}
            {onPreview ? (
              <button
                aria-pressed={previewSelected}
                className={previewSelected ? "preview-button preview-button-selected" : "preview-button"}
                onClick={() => {
                  onPreview(outfit);
                  onClose();
                }}
                type="button"
              >
                {previewSelected ? "Selected for preview" : "Preview on me"}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function OutfitItemTile({ item }: { item: OutfitItem }) {
  return (
    <div className="outfit-item-tile">
      {item.image_url ? (
        // Outfit thumbnails use the owner's scoped URLs; never send them through a public optimizer.
        // eslint-disable-next-line @next/next/no-img-element
        <img alt={`${item.role}: ${item.name}`} src={item.image_url} />
      ) : <span aria-hidden="true">✦</span>}
      <div>
        <small>{humanize(item.role)}</small>
        <strong>{item.name}</strong>
        <span>
          {item.colors.join(" · ") || "Color under review"} · {item.wear_count} wears
          {item.cost_per_wear !== null ? ` · $${item.cost_per_wear.toFixed(2)}/wear` : ""}
        </span>
      </div>
    </div>
  );
}

function todayIso(): string {
  const date = new Date();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
