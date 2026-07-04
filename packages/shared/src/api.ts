import type { AdminOverview, Health, Job, Manifest, Stats } from "./types";

export interface LibraryPage {
  jobs: Job[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}

export interface VerifyResult {
  found: boolean;
  verified: boolean;
  canonical_hash?: string;
  manifest?: Manifest;
  reason?: string;
}

const BASE = import.meta.env.VITE_API_BASE || "";

// Admin bearer token
let adminToken: string | null = null;
export function setAdminToken(token: string | null) {
  adminToken = token;
}
function adminHeaders(): Record<string, string> {
  return adminToken ? { "X-Admin-Token": adminToken } : {};
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json();
}

export const api = {
  // Public / customer
  health: () => fetch(`${BASE}/api/health`).then(j<Health>),
  stats: () => fetch(`${BASE}/api/stats`).then(j<Stats>),
  generate: (brief: Record<string, unknown>) =>
    fetch(`${BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(brief),
    }).then(j<{ job_id: string; status: string }>),
  job: (id: string) => fetch(`${BASE}/api/jobs/${id}`).then(j<Job>),
  library: (limit = 24, offset = 0) =>
    fetch(`${BASE}/api/library?limit=${limit}&offset=${offset}`).then(j<LibraryPage>),
  passport: (id: string) => fetch(`${BASE}/api/passport/${id}`).then(j<Job>),
  downloadUrl: (id: string) => `${BASE}/api/passport/${id}/download`,
  verify: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/api/verify`, { method: "POST", body: fd }).then(j<VerifyResult>);
  },

  // Admin (require a valid admin token)
  adminLogin: (password: string) =>
    fetch(`${BASE}/api/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }).then(j<{ token: string }>),
  adminOverview: () => fetch(`${BASE}/api/admin/overview`, { headers: adminHeaders() }).then(j<AdminOverview>),
  retry: (id: string) =>
    fetch(`${BASE}/api/admin/jobs/${id}/retry`, { method: "POST", headers: adminHeaders() }).then(
      j<{ job_id: string; status: string; retried_from: string }>
    ),
  remove: (id: string) =>
    fetch(`${BASE}/api/admin/jobs/${id}`, { method: "DELETE", headers: adminHeaders() }).then(
      j<{ deleted: string }>
    ),
};

export type { AdminOverview, Asset, Health, Job, Manifest, Stats, StepDetail } from "./types";
