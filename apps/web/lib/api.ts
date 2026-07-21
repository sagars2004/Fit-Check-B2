const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export type Health = {
  status: string;
  app_env: string;
  provider_mode: string;
  storage_mode: string;
  gmi_model_configured: boolean;
};

export type DemoAsset = {
  asset_id: string;
  garment_id: string;
  run_id: string;
  parent_run_id: string | null;
  object_key: string;
  sha256: string;
  manifest_key: string;
  manifest_hash: string;
  evidence_status: string;
  provider: string;
  model: string;
  created_at: string;
};

export type Provenance = {
  entity_type: string;
  entity_id: string;
  manifest: Record<string, unknown>;
};

export async function getHealth(): Promise<Health> {
  const response = await fetch(apiBaseUrl + "/health");
  if (!response.ok) {
    throw new Error("Fit Check API is unavailable.");
  }
  return response.json() as Promise<Health>;
}

export async function createMockCutout(): Promise<DemoAsset> {
  const response = await fetch(apiBaseUrl + "/v1/demo/mock-cutout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ garment_name: "Demo navy overshirt" }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { message?: string } | null;
    throw new Error(body?.message ?? "The mock provenance pipeline did not complete.");
  }
  return response.json() as Promise<DemoAsset>;
}

export async function getProvenance(assetId: string): Promise<Provenance> {
  const response = await fetch(apiBaseUrl + "/v1/provenance/garment_asset/" + assetId);
  if (!response.ok) {
    throw new Error("The asset was created but its provenance record was unavailable.");
  }
  return response.json() as Promise<Provenance>;
}

export function localMockMediaUrl(objectKey: string): string {
  return (
    apiBaseUrl +
    "/v1/media/" +
    objectKey
      .split("/")
      .map((part) => encodeURIComponent(part))
      .join("/")
  );
}

