"use client";

import { useEffect, useState } from "react";
import { getAllRenders, type TryOnRender } from "../lib/api";

export function Gallery() {
  const [renders, setRenders] = useState<TryOnRender[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRenders() {
      try {
        setLoading(true);
        const data = await getAllRenders(20);
        setRenders(data);
      } catch (err: any) {
        setError(err.message || "Failed to load renders");
      } finally {
        setLoading(false);
      }
    }
    fetchRenders();
  }, []);

  if (loading) {
    return <div className="gallery-loading">Loading I'm Feeling Lucky Gallery...</div>;
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
          <img
            src={render.render_url ?? ""}
            alt="AI Preview"
            className="gallery-main-image"
          />
          <div className="gallery-overlay">
            <div className="gallery-sources">
              {render.source_garments.map((garment) => (
                <div key={garment.id} className="gallery-garment">
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
