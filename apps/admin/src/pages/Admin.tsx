import { useEffect, useState } from "react";
import { ApiError, Job, StepDetail } from "@veritas/shared";
import { useAuthStore } from "../stores/useAuthStore";
import { useAdminLibrary, useOverview, useRemove, useRetry } from "../services/adminService";

const MODALITIES = ["image", "video", "audio"];
const CUSTOMER_URL = import.meta.env.VITE_CUSTOMER_URL || "http://localhost:5173";

function isAuthError(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 401 || e.status === 403);
}

export default function Admin() {
  const logout = useAuthStore((s) => s.logout);
  const [live, setLive] = useState(true);
  const poll = live ? 3000 : undefined;

  const overview = useOverview({ poll });
  const library = useAdminLibrary({ poll });
  const retry = useRetry();
  const remove = useRemove();

  // An expired/invalid token surfaces as a 401/403 on the polling queries → sign out.
  const authExpired = isAuthError(overview.error) || isAuthError(library.error);
  useEffect(() => {
    if (authExpired) logout();
  }, [authExpired, logout]);

  const ov = overview.data ?? null;
  const jobs = library.data ?? [];
  const busy = retry.isPending ? retry.variables : remove.isPending ? remove.variables : null;
  const err =
    overview.error && !isAuthError(overview.error) ? (overview.error as Error).message : null;

  function onRetry(id: string) {
    retry.mutate(id, { onError: (e) => alert((e as Error).message) });
  }
  function onDelete(id: string) {
    if (!confirm("Delete this run from the index? (B2 assets are not deleted)")) return;
    remove.mutate(id, { onError: (e) => alert((e as Error).message) });
  }

  const h = ov?.health;
  const s = ov?.stats;
  const credit = ov?.recent_errors?.some((e) => /credit|402|insufficient/i.test(e.error || ""));

  return (
    <>
      <nav className="nav">
        <span className="brand">
          <span className="dot" /> Veritas <span className="muted font-medium">· Admin</span>
        </span>
        <div className="spacer" />
        <a className="badge" href={CUSTOMER_URL} target="_blank" rel="noreferrer">
          ↗ Customer app
        </a>
        <button className="btn small ghost ml-3" onClick={logout}>
          Sign out
        </button>
      </nav>

      <div className="container wide">
        <div className="spread">
          <div>
            <h1 className="m-0 text-[28px] tracking-[-0.5px]">Operations</h1>
            <p className="muted small mt-1">
              Live monitor for generation runs, provider health, and B2 orchestration.
            </p>
          </div>
          <label className="row small cursor-pointer gap-2">
            <input
              type="checkbox"
              className="w-auto"
              checked={live}
              onChange={(e) => setLive(e.target.checked)}
            />
            Live (3s)
          </label>
        </div>

        {err && <div className="banner bad mt-4">{err}</div>}

        {/* System status */}
        <div className="card mt-5">
          <div className="spread">
            <div className="row gap-2.5">
              <span className={`tag ${h?.ok ? "good" : "bad"}`}>
                {h?.ok ? "● Backend healthy" : "● Backend degraded"}
              </span>
              {h?.missing_keys?.length ? (
                <span className="tag bad">Missing: {h.missing_keys.join(", ")}</span>
              ) : (
                <span className="tag muted">Credentials OK</span>
              )}
              <span className="tag muted">bucket: {h?.bucket || "—"}</span>
              <span className="tag muted">mode: {h?.pipeline_mode}</span>
            </div>
            <div className="row small muted">
              <span>img: {h?.models.image}</span>·<span>vid: {h?.models.video}</span>·
              <span>aud: {h?.models.audio}</span>
            </div>
          </div>
        </div>

        {credit && (
          <div className="banner warn mt-4">
            ⚠ A recent run failed with an <b>insufficient-credits (402)</b> error from GMI Cloud.
            Top up your GMI credits so the video step can run.
          </div>
        )}

        {/* Metrics */}
        <div className="stat-grid my-4.5">
          <Stat n={s?.runs} l="Runs" />
          <Stat n={s?.running} l="In progress" accent="text-warn" />
          <Stat n={s?.completed} l="Completed" accent="text-good" />
          <Stat n={s?.failed} l="Failed" accent="text-bad" />
          <Stat n={s?.verified} l="Verified" accent="text-teal" />
          <Stat n={s?.assets} l="Assets on B2" />
          <Stat n={s ? `$${s.total_cost_usd}` : undefined} l="Gen cost" />
        </div>

        {/* Recent errors */}
        {ov?.recent_errors?.length ? (
          <>
            <div className="section-title">Recent errors</div>
            <div className="card p-0">
              {ov.recent_errors.map((e, i) => (
                <div key={i} className="err-row">
                  <span className="tag bad shrink-0">error</span>
                  <span className="small min-w-40 text-ink">{e.title || e.id}</span>
                  <span className="mono small text-muted">{e.error}</span>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {/* Jobs monitor — table on desktop, stacked cards on mobile */}
        <div className="section-title">Run monitor</div>

        <div className="card hidden overflow-x-auto p-0 md:block">
          <table className="tbl">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Pipeline steps</th>
                <th>Cost</th>
                <th>Verified</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <div className="font-semibold">{job.title || job.id}</div>
                    <div className="mono text-[11px] text-muted">{job.id}</div>
                  </td>
                  <td>
                    <JobStatus job={job} />
                  </td>
                  <td>
                    <Steps job={job} />
                  </td>
                  <td className="small">${(job.cost_usd || 0).toFixed(3)}</td>
                  <td>
                    {job.verified ? (
                      <span className="tag good">✓</span>
                    ) : (
                      <span className="tag muted">—</span>
                    )}
                  </td>
                  <td>
                    <RunActions job={job} busy={busy} onRetry={onRetry} onDelete={onDelete} />
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted small p-5">
                    No runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card p-0 md:hidden">
          {jobs.length === 0 && <div className="muted small p-4">No runs yet.</div>}
          {jobs.map((job) => (
            <div key={job.id} className="run-card">
              <div className="spread">
                <div className="min-w-0">
                  <div className="truncate font-semibold">{job.title || job.id}</div>
                  <div className="mono text-[11px] text-muted">{job.id}</div>
                </div>
                <JobStatus job={job} />
              </div>
              <Steps job={job} />
              <div className="spread">
                <span className="small muted">
                  ${(job.cost_usd || 0).toFixed(3)} · {job.verified ? "✓ verified" : "unverified"}
                </span>
                <RunActions job={job} busy={busy} onRetry={onRetry} onDelete={onDelete} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function RunActions({
  job,
  busy,
  onRetry,
  onDelete,
}: {
  job: Job;
  busy: string | null | undefined;
  onRetry: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="row gap-1.5">
      <a
        className="btn small ghost"
        href={`${CUSTOMER_URL}/passport/${job.id}`}
        target="_blank"
        rel="noreferrer"
      >
        View
      </a>
      <button
        className="btn small ghost"
        disabled={busy === job.id}
        onClick={() => onRetry(job.id)}
      >
        Retry
      </button>
      <button
        className="btn small ghost danger"
        disabled={busy === job.id}
        onClick={() => onDelete(job.id)}
      >
        Del
      </button>
    </div>
  );
}

function Stat({ n, l, accent }: { n: number | string | undefined; l: string; accent?: string }) {
  return (
    <div className="stat">
      <div className={`n ${accent || ""}`}>{n ?? "—"}</div>
      <div className="l">{l}</div>
    </div>
  );
}

function JobStatus({ job }: { job: Job }) {
  if (job.status === "failed") return <span className="tag bad">Failed</span>;
  if (job.partial) return <span className="tag warn">Partial</span>;
  if (job.status === "completed") return <span className="tag good">Completed</span>;
  return (
    <span className="tag muted">
      <span className="spinner h-2.75 w-2.75" /> {job.stage}
    </span>
  );
}

function stepFor(job: Job, modality: string): StepDetail | undefined {
  const s = (job.steps || []).find((x) => (x.modality || "").toLowerCase().includes(modality));
  if (s) return s;
  const a = job.assets.find((x) => (x.modality || "").toLowerCase().includes(modality));
  if (a)
    return {
      index: a.step_index,
      provider: a.provider,
      model: a.model,
      modality,
      status: "succeeded",
      error: null,
      error_code: null,
      retries: 0,
      cost_usd: null,
      url: a.url,
    };
  return undefined;
}

function Steps({ job }: { job: Job }) {
  const mods = job.steps?.length
    ? MODALITIES.filter((m) => job.steps!.some((s) => (s.modality || "").toLowerCase().includes(m)))
    : MODALITIES;
  return (
    <div className="row gap-1.5">
      {mods.map((m) => {
        const st = stepFor(job, m);
        const ok = st && /succeed|complete/i.test(st.status || "");
        const failed = st && (st.error || /fail/i.test(st.status || ""));
        const cls = ok ? "good" : failed ? "bad" : "muted";
        const glyph = ok ? "✓" : failed ? "✕" : job.status === "running" ? "…" : "·";
        return (
          <span key={m} className={`chip ${cls}`} title={st?.error || st?.status || "pending"}>
            {glyph} {m}
          </span>
        );
      })}
    </div>
  );
}
