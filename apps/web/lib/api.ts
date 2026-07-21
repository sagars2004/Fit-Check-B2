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

export type UploadTarget = {
  upload_id: string;
  mode: "api_proxy" | "direct_b2";
  upload_url: string;
  original_key: string;
  expires_in_seconds: number | null;
  duplicate: boolean;
};

export type UploadResult = {
  upload_id: string;
  status: string;
  duplicate: boolean;
  duplicate_of_upload_id: string | null;
  sha256: string;
  width: number | null;
  height: number | null;
  normalized_key: string | null;
};

export type ImportJob = {
  id: string;
  status: string;
  progress: number;
  upload_ids: string[];
  candidate_ids: string[];
  candidate_count: number;
  error_code: string | null;
  error_message: string | null;
  stages: string[];
};

export type Candidate = {
  id: string;
  upload_id: string;
  import_job_id: string | null;
  bbox: Record<string, number>;
  attributes: {
    name_suggestion?: string;
    category?: string;
    colors?: string[];
    tags?: string[];
    apparent_material?: string;
    pattern?: string;
    [key: string]: unknown;
  };
  unresolved_details: string[];
  confidence: number;
  status: string;
  source_crop_key: string | null;
  source_crop_url: string | null;
  reviewer_notes: string | null;
  garment_id: string | null;
  created_at: string;
};

export type Garment = {
  id: string;
  name: string;
  category: string;
  colors: string[];
  tags: string[];
  seasons: string[];
  price: number | null;
  purchase_date: string | null;
  notes: string | null;
  wear_count: number;
  status: string;
  evidence_status: "verified_source_backed" | "ai_reconstructed" | "needs_better_photo";
  source_crop_key: string | null;
  source_crop_url: string | null;
  canonical_asset_id: string | null;
  cutouts: GarmentAsset[];
  created_at: string;
};

export type GarmentAsset = {
  id: string;
  kind: string;
  object_key: string;
  asset_url: string | null;
  sha256: string;
  version: number;
  qa_status: "awaiting_review" | "approved" | "rejected" | "failed" | string;
  qa_warnings: string[];
  evidence_status: "verified_source_backed" | "ai_reconstructed" | "needs_better_photo" | string;
  run_id: string | null;
  parent_run_id: string | null;
  provider: string;
  model: string;
  approved_at: string | null;
  created_at: string;
};

export type DuplicateGarmentReference = {
  id: string;
  name: string;
  category: string;
  colors: string[];
  source_crop_url: string | null;
  cutout_url: string | null;
};

export type DuplicateReview = {
  id: string;
  score: number;
  evidence: Record<string, unknown>;
  status: "pending" | "not_duplicate" | "likely_duplicate" | string;
  reviewer_notes: string | null;
  garment_a: DuplicateGarmentReference;
  garment_b: DuplicateGarmentReference;
  created_at: string;
};

export type CandidateReview = {
  action: "approve" | "edit" | "reject" | "hold";
  name?: string;
  category?: string;
  colors?: string[];
  tags?: string[];
  notes?: string;
};

export type GarmentUpdate = {
  name?: string;
  category?: string;
  colors?: string[];
  tags?: string[];
  seasons?: string[];
  price?: number;
  purchase_date?: string;
  notes?: string;
  archive?: boolean;
};

export type WeatherSnapshot = {
  location: string;
  forecast_date: string;
  low_c: number;
  high_c: number;
  apparent_high_c: number;
  precipitation_probability: number;
  precipitation_mm: number;
  weather_code: number;
  wind_kph: number;
  condition: string;
  source: string;
  advisory: string | null;
};

export type OutfitItem = {
  garment_id: string;
  role: "top" | "bottom" | "one_piece" | "outerwear" | "footwear" | "accessory" | string;
  name: string;
  category: string;
  colors: string[];
  tags: string[];
  wear_count: number;
  price: number | null;
  cost_per_wear: number | null;
  evidence_status: "verified_source_backed" | "ai_reconstructed" | "needs_better_photo" | string;
  image_url: string | null;
};

export type OutfitPlan = {
  id: string;
  title: string;
  weather: WeatherSnapshot;
  occasion: string;
  score: number;
  reasoning: string;
  status: "proposed" | "saved" | "worn" | string;
  planner_run_id: string | null;
  items: OutfitItem[];
  created_at: string;
};

export type OutfitRecommendation = {
  weather: WeatherSnapshot;
  occasion: string;
  options: OutfitPlan[];
  warnings: string[];
};

export type WearEvent = {
  event_id: string;
  outfit_id: string;
  action: "wear" | "undo";
  worn_on: string;
  outfit_status: string;
  garment_wear_counts: Record<string, number>;
  garment_cost_per_wear: Record<string, number | null>;
};

export async function getHealth(): Promise<Health> {
  return requestJson<Health>("/health");
}

export async function createMockCutout(): Promise<DemoAsset> {
  return requestJson<DemoAsset>("/v1/demo/mock-cutout", {
    method: "POST",
    body: JSON.stringify({ garment_name: "Demo navy overshirt" }),
  });
}

export async function getProvenance(assetId: string): Promise<Provenance> {
  return requestJson<Provenance>("/v1/provenance/garment_asset/" + assetId);
}

export async function uploadPhotos(files: File[]): Promise<{ uploads: UploadResult[]; errors: string[] }> {
  const uploads: UploadResult[] = [];
  const errors: string[] = [];

  for (const file of files) {
    try {
      const target = await requestJson<UploadTarget>("/v1/uploads/presign", {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type || guessContentType(file.name),
          size_bytes: file.size,
        }),
      });
      const destination = absoluteApiUrl(target.upload_url);
      const response = await fetch(destination, {
        method: "PUT",
        headers: { "Content-Type": file.type || guessContentType(file.name) },
        body: file,
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response, "This photo could not be saved securely."));
      }
      if (target.mode === "api_proxy") {
        uploads.push((await response.json()) as UploadResult);
      } else {
        // The API validates the private B2 object and computes its SHA-256 when
        // the import is created. The browser does not need B2 credentials.
        uploads.push({
          upload_id: target.upload_id,
          status: "pending_validation",
          duplicate: false,
          duplicate_of_upload_id: null,
          sha256: "",
          width: null,
          height: null,
          normalized_key: null,
        });
      }
    } catch (caught: unknown) {
      errors.push(`${file.name}: ${caught instanceof Error ? caught.message : "Upload failed."}`);
    }
  }
  return { uploads, errors };
}

export async function createImport(uploadIds: string[]): Promise<ImportJob> {
  return requestJson<ImportJob>("/v1/imports", {
    method: "POST",
    body: JSON.stringify({ upload_ids: uploadIds }),
  });
}

export async function getImport(importId: string): Promise<ImportJob> {
  return requestJson<ImportJob>(`/v1/imports/${importId}`);
}

export async function getCandidates(): Promise<Candidate[]> {
  return requestJson<Candidate[]>("/v1/candidates");
}

export async function reviewCandidate(id: string, review: CandidateReview): Promise<Candidate> {
  return requestJson<Candidate>(`/v1/candidates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(review),
  });
}

export async function getGarments(): Promise<Garment[]> {
  return requestJson<Garment[]>("/v1/garments");
}

export async function updateGarment(id: string, update: GarmentUpdate): Promise<Garment> {
  return requestJson<Garment>(`/v1/garments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function generateCutout(id: string): Promise<GarmentAsset> {
  return requestJson<GarmentAsset>(`/v1/garments/${id}/generate-cutout`, {
    method: "POST",
  });
}

export async function reviewCutout(
  garmentId: string,
  assetId: string,
  action: "approve" | "reject",
): Promise<GarmentAsset> {
  return requestJson<GarmentAsset>(`/v1/garments/${garmentId}/cutouts/${assetId}/review`, {
    method: "PATCH",
    body: JSON.stringify({ action }),
  });
}

export async function getDuplicateReviews(): Promise<DuplicateReview[]> {
  return requestJson<DuplicateReview[]>("/v1/duplicate-reviews");
}

export async function decideDuplicateReview(
  reviewId: string,
  action: "keep_separate" | "mark_likely_duplicate",
): Promise<DuplicateReview> {
  return requestJson<DuplicateReview>(`/v1/duplicate-reviews/${reviewId}`, {
    method: "PATCH",
    body: JSON.stringify({ action }),
  });
}

export async function recommendOutfits(request: {
  location?: string;
  forecast_date: string;
  occasion: string;
  utilization_mode: boolean;
}): Promise<OutfitRecommendation> {
  return requestJson<OutfitRecommendation>("/v1/outfits/recommend", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getOutfits(status?: string): Promise<OutfitPlan[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<OutfitPlan[]>(`/v1/outfits${query}`);
}

export async function saveOutfit(outfitId: string): Promise<OutfitPlan> {
  return requestJson<OutfitPlan>(`/v1/outfits/${outfitId}/save`, { method: "POST" });
}

export async function recordOutfitWear(
  outfitId: string,
  action: "wear" | "undo",
  wornOn: string,
): Promise<WearEvent> {
  return requestJson<WearEvent>(`/v1/outfits/${outfitId}/wear`, {
    method: "POST",
    body: JSON.stringify({ action, worn_on: wornOn }),
  });
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

function absoluteApiUrl(path: string): string {
  return path.startsWith("http://") || path.startsWith("https://") ? path : apiBaseUrl + path;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(absoluteApiUrl(path), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    throw new Error(await responseMessage(response, "Fit Check could not complete that request."));
  }
  return response.json() as Promise<T>;
}

async function responseMessage(response: Response, fallback: string): Promise<string> {
  const body = (await response.json().catch(() => null)) as
    | { message?: string; detail?: string }
    | null;
  return body?.message ?? body?.detail ?? fallback;
}

function guessContentType(filename: string): string {
  const extension = filename.split(".").pop()?.toLowerCase();
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return "image/jpeg";
}
