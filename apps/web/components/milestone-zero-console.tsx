"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createMockCutout,
  getHealth,
  getProvenance,
  localMockMediaUrl,
  type DemoAsset,
  type Health,
  type Provenance,
} from "../lib/api";

type LoadState = "idle" | "loading" | "ready" | "error";

export function MilestoneZeroConsole() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthState, setHealthState] = useState<LoadState>("loading");
  const [runState, setRunState] = useState<LoadState>("idle");
  const [asset, setAsset] = useState<DemoAsset | null>(null);
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = useCallback(async () => {
    setHealthState("loading");
    setError(null);
    try {
      const result = await getHealth();
      setHealth(result);
      setHealthState("ready");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Unable to reach the API.");
      setHealthState("error");
    }
  }, []);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  async function runMockPipeline() {
    setRunState("loading");
    setError(null);
    try {
      const created = await createMockCutout();
      const provenanceRecord = await getProvenance(created.asset_id);
      setAsset(created);
      setProvenance(provenanceRecord);
      setRunState("ready");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The mock pipeline failed.");
      setRunState("error");
    }
  }

  const infrastructureReady = healthState === "ready" && health?.provider_mode === "mock";

  return (
    <section
      aria-busy={healthState === "loading" || runState === "loading"}
      aria-labelledby="m0-heading"
      className="console-card"
    >
      <div className="console-heading">
        <div>
          <p className="eyebrow">Milestone 0 · durable media proof</p>
          <h2 id="m0-heading">Trace one asset from generation to manifest.</h2>
        </div>
        <span className={infrastructureReady ? "status-pill status-ready" : "status-pill"}>
          {healthState === "loading"
            ? "Checking API"
            : infrastructureReady
              ? "Mock mode ready"
              : "Needs setup"}
        </span>
      </div>

      <p className="console-copy">
        This offline run makes a clearly labeled AI-reconstructed demo cutout, validates its alpha
        channel locally, writes it to local storage or B2, and persists a hash-verified provenance
        manifest. It never claims to be a source-backed wardrobe item.
      </p>

      <div className="readiness-grid" aria-label="Runtime status">
        <StatusCell label="Provider" value={health?.provider_mode ?? "…"} />
        <StatusCell label="Storage" value={health?.storage_mode ?? "…"} />
        <StatusCell
          label="GMI model"
          value={health?.gmi_model_configured ? "configured" : "awaiting smoke test"}
        />
      </div>

      <button
        className="primary-button"
        disabled={!infrastructureReady || runState === "loading"}
        onClick={() => void runMockPipeline()}
        type="button"
      >
        {runState === "loading" ? "Writing asset + manifest…" : "Run mock provenance pipeline"}
      </button>

      {error ? (
        <div className="error-message" role="alert">
          <p>{error}</p>
          {healthState === "error" ? (
            <button className="inline-retry-button" onClick={() => void loadHealth()} type="button">
              Try the API check again
            </button>
          ) : null}
        </div>
      ) : null}

      {asset ? (
        <div className="artifact-result">
          <div className="asset-preview">
            <div className="checkerboard">
              {/* Local/B2 private media uses a scoped URL; do not proxy personal wardrobe images through a public optimizer. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt="A deliberately generic mock garment silhouette with a transparent background"
                src={localMockMediaUrl(asset.object_key)}
              />
            </div>
            <p>AI-reconstructed demo asset — human review required</p>
          </div>

          <div className="artifact-metadata">
            <p className="eyebrow">Stored artifact</p>
            <dl>
              <MetadataTerm label="Provider" value={asset.provider + " / " + asset.model} />
              <MetadataTerm label="Asset SHA-256" value={shortHash(asset.sha256)} />
              <MetadataTerm label="Run" value={asset.run_id} />
              <MetadataTerm label="Manifest hash" value={shortHash(asset.manifest_hash)} />
              <MetadataTerm label="Object key" value={asset.object_key} />
            </dl>
          </div>
        </div>
      ) : null}

      {provenance ? (
        <details className="provenance-panel">
          <summary>How this was made</summary>
          <pre>{JSON.stringify(provenance.manifest, null, 2)}</pre>
        </details>
      ) : null}
    </section>
  );
}

function StatusCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetadataTerm({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd title={value}>{value}</dd>
    </div>
  );
}

function shortHash(value: string) {
  return value.length > 18 ? value.slice(0, 10) + "…" + value.slice(-7) : value;
}
