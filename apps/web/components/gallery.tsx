"use client";

import { useEffect, useState } from "react";
import { deleteRender, getAllRenders, type TryOnRender } from "../lib/api";

export function Gallery() {
  const [renders, setRenders] = useState<TryOnRender[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRenders() {
      try {
        setLoading(true);
        const data = await getAllRenders(20);
        setRenders(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load renders");
      } finally {
        setLoading(false);
      }
    }
    fetchRenders();
  }, []);

  async function handleDelete(renderId: string) {
    setDeletingId(renderId);
    try {
      await deleteRender(renderId);
      setRenders((current) => current.filter((r) => r.id !== renderId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not delete this preview tile.");
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <div className="gallery-loading">Loading I&apos;m Feeling Lucky Gallery...</div>;
  }

  if (error) {
    return <div className="gallery-error">{error}</div>;
  }

  if (renders.length === 0) {
    return (
      <div className="gallery-empty">
        <p>No looks generated yet. Head to the Studio to generate some outfits!</p>
      </div>
    );
  }

  return (
    <div className="gallery-grid">
      {renders.map((render) => (
        <div key={render.id} className="gallery-item">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={render.render_url ?? ""}
            alt="AI Preview"
            className="gallery-main-image"
          />
          <div className="gallery-overlay">
            <button
              className="gallery-delete-btn"
              disabled={deletingId === render.id}
              onClick={() => void handleDelete(render.id)}
              title="Delete tile"
              type="button"
            >
              {deletingId === render.id ? "…" : "✕"}
            </button>
            <div className="gallery-sources">
              {render.source_garments.map((garment) => (
                <div key={garment.id} className="gallery-garment">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={garment.image_url ?? ""}
                    alt={garment.name}
                    title={garment.name}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

