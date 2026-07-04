// Shared domain types used by both the customer and admin apps.

// A Genblaze provenance manifest. Its internal shape is owned by the SDK and
// surfaced verbatim in the Passport UI, so we keep it as an opaque object rather
// than an `any` — callers read known top-level fields defensively.
export type Manifest = Record<string, unknown>;

export interface Asset {
  id: string;
  step_index: number;
  modality: string | null;
  provider: string | null;
  model: string | null;
  url: string | null;
  sha256: string | null;
  media_type: string | null;
}

export interface StepDetail {
  index: number;
  provider: string | null;
  model: string | null;
  modality: string | null;
  status: string | null;
  error: string | null;
  error_code: string | null;
  retries: number;
  cost_usd: number | null;
  url: string | null;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string | null;
  title: string | null;
  error: string | null;
  run_id: string | null;
  parent_run_id: string | null;
  manifest_uri: string | null;
  manifest_hash: string | null;
  verified: boolean;
  partial?: boolean;
  cost_usd: number;
  created_at: number | null;
  updated_at?: number | null;
  assets: Asset[];
  steps?: StepDetail[];
  brief?: Record<string, unknown>;
  plan?: {
    title: string;
    image_prompt: string;
    video_prompt: string;
    voiceover: string;
    tone: string;
  };
  manifest?: Manifest;
}

export interface Health {
  ok: boolean;
  missing_keys: string[];
  pipeline_mode: string;
  bucket: string | null;
  models: { image: string; video: string; audio: string };
}

export interface Stats {
  runs: number;
  completed: number;
  failed: number;
  running: number;
  verified: number;
  assets: number;
  total_cost_usd: number;
}

export interface AdminOverview {
  health: Health;
  stats: Stats;
  recent_errors: { id: string; title: string | null; error: string | null; updated_at: number }[];
}
