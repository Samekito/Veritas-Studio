import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronsUpDown } from "lucide-react";
import { Job } from "@veritas/shared";
import AssetView from "./AssetView";
import { useGenerate, useHealth, useJob } from "../services/jobsService";

const TONES = ["cinematic", "energetic", "elegant", "playful", "corporate", "futuristic"];

const STAGES = [
  "Planning",
  "Rendering keyframe image",
  "Animating video",
  "Generating voiceover",
  "Completed",
];

export default function Home() {
  const { data: health } = useHealth();
  const [form, setForm] = useState({
    subject: "",
    audience: "",
    tone: "cinematic",
    message: "",
    cta: "",
  });
  const [jobId, setJobId] = useState<string | null>(null);
  const generate = useGenerate();
  const { data: job } = useJob(jobId, { poll: true });

  const submitting = generate.isPending;
  const err = generate.isError ? (generate.error as Error).message : null;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    generate.mutate(form, { onSuccess: ({ job_id }) => setJobId(job_id) });
  }

  const running = job && (job.status === "queued" || job.status === "running");
  const stageIdx = job ? STAGES.findIndex((s) => s === job.stage) : -1;

  return (
    <div className="container">
      <div className="hero">
        <h1>
          Generate media you can <span className="grad">prove</span>.
        </h1>
        <p>
          Veritas Studio turns a one-line brief into a campaign-ready clip through a multi-model
          Genblaze pipeline — and stamps every asset with a cryptographic <b>Content Passport</b>,
          stored and orchestrated on Backblaze B2.
        </p>
        <div className="pill-row">
          <span className="pill">text → image → video → voiceover</span>
          <span className="pill">SHA-256 provenance manifest</span>
          <span className="pill">multi-provider fallback</span>
          <span className="pill">B2 content-addressable storage</span>
        </div>
      </div>

      {health && !health.ok && (
        <div className="banner bad mt-7">
          Backend isn’t fully configured. Missing: <b>{health.missing_keys.join(", ")}</b>. Fill{" "}
          <span className="mono">backend/.env</span> and restart the API.
        </div>
      )}

      <div className="grid two mt-7">
        <form className="card" onSubmit={submit}>
          <div className="field">
            <label>What are we promoting? *</label>
            <input
              required
              placeholder="e.g. a minimalist titanium water bottle"
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Audience</label>
            <input
              placeholder="e.g. urban commuters who care about design"
              value={form.audience}
              onChange={(e) => setForm({ ...form, audience: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Tone</label>
            <div style={{ position: "relative" }}>
              <select
                value={form.tone}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
                style={{ paddingRight: "2.25rem" }}
              >
                {TONES.map((t) => (
                  <option key={t} value={t}>
                    {t[0].toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
              <ChevronsUpDown
                size={15}
                style={{
                  position: "absolute",
                  right: "0.75rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  pointerEvents: "none",
                  opacity: 0.45,
                }}
              />
            </div>
          </div>
          <div className="field">
            <label>Key message (optional)</label>
            <textarea
              placeholder="The hook your voiceover should open with"
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Call to action</label>
            <input
              placeholder="e.g. Stay hydrated. Stay sharp."
              value={form.cta}
              onChange={(e) => setForm({ ...form, cta: e.target.value })}
            />
          </div>
          <button className="btn" disabled={submitting || !!running || !form.subject}>
            {submitting || running ? <span className="spinner" /> : null}
            {running ? "Generating…" : "Generate verifiable clip"}
          </button>
          {err && <div className="banner bad mt-4">{err}</div>}
          {health && (
            <p className="muted small mt-4">
              Models: {health.models.image} · {health.models.video} · {health.models.audio} · mode{" "}
              <b>{health.pipeline_mode}</b>
            </p>
          )}
        </form>

        <div className="card">
          {!job && (
            <div className="muted">
              <div className="section-title mt-0">How it works</div>
              <ol className="list-decimal pl-4.5 leading-[1.9]">
                <li>Your brief is expanded into image, motion &amp; voiceover prompts.</li>
                <li>Genblaze runs a chained, multi-model pipeline with automatic fallback.</li>
                <li>Each asset + a tamper-evident manifest is written to Backblaze B2.</li>
                <li>You get a public Content Passport that anyone can verify.</li>
              </ol>
            </div>
          )}

          {job && (
            <>
              <div className="spread">
                <div className="section-title m-0">{job.title || "Run"}</div>
                <StatusTag job={job} />
              </div>

              <div className="steps mt-4">
                {STAGES.slice(0, 4).map((s, i) => {
                  const done = job.status === "completed" || (stageIdx > i && stageIdx >= 0);
                  const active = running && stageIdx === i;
                  return (
                    <div key={s} className={`step ${done ? "done" : ""} ${active ? "active" : ""}`}>
                      <span className="ring">{done ? "✓" : i + 1}</span>
                      <span>{s}</span>
                    </div>
                  );
                })}
              </div>

              {job.status === "failed" && <div className="banner bad mt-4">{job.error}</div>}

              {job.status === "completed" && (
                <div className="mt-4.5">
                  <AssetView job={job} />
                  <Link className="btn small mt-3.5" to={`/passport/${job.id}`}>
                    View Content Passport →
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusTag({ job }: { job: Job }) {
  if (job.status === "completed")
    return (
      <span className={`tag ${job.verified ? "good" : "warn"}`}>
        {job.verified ? "✓ Verified" : "Completed"}
      </span>
    );
  if (job.status === "failed") return <span className="tag bad">Failed</span>;
  return (
    <span className="tag muted">
      <span className="spinner h-3 w-3" /> {job.stage}
    </span>
  );
}
