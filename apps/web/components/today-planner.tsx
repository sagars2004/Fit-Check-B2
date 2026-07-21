"use client";

import { type FormEvent, useMemo, useState } from "react";

import {
  type OutfitItem,
  type OutfitPlan,
  type OutfitRecommendation,
  recordOutfitWear,
  recommendOutfits,
  saveOutfit,
} from "../lib/api";

type ActiveAction = { outfitId: string; kind: "save" | "wear" | "undo" } | null;

export function TodayPlanner() {
  const [location, setLocation] = useState("New York, NY");
  const [forecastDate, setForecastDate] = useState(todayIso());
  const [occasion, setOccasion] = useState("Rainy workday");
  const [utilizationMode, setUtilizationMode] = useState(false);
  const [recommendation, setRecommendation] = useState<OutfitRecommendation | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [activeAction, setActiveAction] = useState<ActiveAction>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const weatherSourceLabel = useMemo(() => {
    if (!recommendation) return null;
    return recommendation.weather.source === "open_meteo" ? "Live Open-Meteo" : "Local demo forecast";
  }, [recommendation]);

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
        `${next.options.length} owned-only look${next.options.length === 1 ? "" : "s"} planned. No image generation was used.`,
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
      setNotice("Saved this owned-only look. Its garments and source evidence stay unchanged.");
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
          ? "Wear logged. Each garment's use count was incremented."
          : "Wear log reversed. Each garment's use count was restored.",
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
    <section className="today-planner" aria-labelledby="today-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Milestone 2 · today</p>
          <h2 id="today-heading">A useful answer for the day you actually have.</h2>
        </div>
        <span className="status-pill status-ready">Owned-only planner</span>
      </div>
      <p className="workbench-copy">
        Fit Check applies weather, occasion, palette, recent wear, and optional utilization rules locally.
        Every option is validated against your approved wardrobe before it appears.
      </p>

      <form className="today-context" onSubmit={(event) => void handlePlan(event)}>
        <label>
          Location
          <input onChange={(event) => setLocation(event.target.value)} placeholder="New York, NY" value={location} />
        </label>
        <label>
          Date
          <input onChange={(event) => setForecastDate(event.target.value)} type="date" value={forecastDate} />
        </label>
        <label className="occasion-field">
          Occasion or context
          <input
            onChange={(event) => setOccasion(event.target.value)}
            placeholder="Rainy commute, dinner after work"
            value={occasion}
          />
        </label>
        <label className="utilization-toggle">
          <input
            checked={utilizationMode}
            onChange={(event) => setUtilizationMode(event.target.checked)}
            type="checkbox"
          />
          <span>
            <strong>Utilization mode</strong>
            <small>Gently favor compatible pieces with fewer wears.</small>
          </span>
        </label>
        <button className="primary-button" disabled={isPlanning} type="submit">
          {isPlanning ? "Planning owned looks…" : "Plan three looks"}
        </button>
      </form>

      {notice ? <p className="success-message" role="status">{notice}</p> : null}
      {error ? <p className="error-message" role="alert">{error}</p> : null}

      {recommendation ? (
        <>
          <section className="forecast-card" aria-label="Forecast context">
            <div>
              <p className="eyebrow">Forecast · {weatherSourceLabel}</p>
              <h3>{recommendation.weather.location}</h3>
              <p>{formatDate(recommendation.weather.forecast_date)} · {recommendation.weather.condition}</p>
            </div>
            <dl>
              <div><dt>Temperature</dt><dd>{Math.round(recommendation.weather.low_c)}–{Math.round(recommendation.weather.high_c)}°C</dd></div>
              <div><dt>Rain</dt><dd>{recommendation.weather.precipitation_probability}% · {recommendation.weather.precipitation_mm} mm</dd></div>
              <div><dt>Wind</dt><dd>{Math.round(recommendation.weather.wind_kph)} km/h</dd></div>
            </dl>
            {recommendation.weather.advisory ? <p className="forecast-advisory">{recommendation.weather.advisory}</p> : null}
          </section>

          {recommendation.warnings.length > 0 ? (
            <section className="planner-warnings" aria-label="Wardrobe coverage notes">
              <strong>Wardrobe coverage note</strong>
              <ul>{recommendation.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          ) : null}

          <div className="recommendation-heading">
            <div>
              <p className="eyebrow">Three valid options</p>
              <h3>For {recommendation.occasion}</h3>
            </div>
            <span>Rules first · explanation second</span>
          </div>
          <div className="outfit-grid">
            {recommendation.options.map((outfit, index) => (
              <OutfitCard
                activeAction={activeAction}
                key={outfit.id}
                onSave={handleSave}
                onWear={handleWear}
                outfit={outfit}
                rank={index + 1}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="empty-state">Choose a date and occasion to plan from your approved wardrobe. Held items and unreviewed candidates are excluded.</p>
      )}
    </section>
  );
}

function OutfitCard({
  activeAction,
  onSave,
  onWear,
  outfit,
  rank,
}: {
  activeAction: ActiveAction;
  onSave: (outfitId: string) => Promise<void>;
  onWear: (outfit: OutfitPlan, action: "wear" | "undo") => Promise<void>;
  outfit: OutfitPlan;
  rank: number;
}) {
  const saving = activeAction?.outfitId === outfit.id;
  return (
    <article className="outfit-card">
      <div className="outfit-card-meta">
        <span className="review-badge">Option {rank}</span>
        <span>{Math.round(outfit.score)} suitability</span>
      </div>
      <h4>{outfit.title}</h4>
      <p className="outfit-reasoning">{outfit.reasoning}</p>
      <div className="outfit-items" aria-label={`Garments in ${outfit.title}`}>
        {outfit.items.map((item) => <OutfitItemTile item={item} key={`${outfit.id}-${item.garment_id}`} />)}
      </div>
      <p className="outfit-disclosure">Approved owned garments only · no try-on image has been generated.</p>
      <div className="review-actions">
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
      </div>
    </article>
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
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
