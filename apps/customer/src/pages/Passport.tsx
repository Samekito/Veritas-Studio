import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@veritas/shared";
import AssetView from "./AssetView";
import { usePassport } from "../services/jobsService";

export default function Passport() {
  const { id } = useParams();
  const { data: job, error } = usePassport(id);
  const [showJson, setShowJson] = useState(false);

  if (error)
    return (
      <div className="container">
        <div className="banner bad">{(error as Error).message}</div>
      </div>
    );
  if (!job)
    return (
      <div className="container">
        <p className="muted">Loading passport…</p>
      </div>
    );

  // The manifest's internal shape is owned by the Genblaze SDK; read the lineage
  // steps through a narrow cast at this boundary rather than typing the whole tree.
  const manifest = job.manifest as { run?: { steps?: unknown[] } } | undefined;
  const steps = (manifest?.run?.steps as Array<Record<string, unknown>>) || [];

  return (
    <div className="container">
      <Link to="/library" className="muted small hover:text-gray-400">
        Go back to Library
      </Link>
      <div className="spread mb-1 mt-2.5">
        <h1 className="m-0 text-[28px] tracking-[-0.5px]">{job.title}</h1>
        {job.verified ? (
          <span className="tag good px-3.5 py-2 text-sm">✓ Provenance Verified</span>
        ) : (
          <span className="tag warn px-3.5 py-2 text-sm">Unverified</span>
        )}
      </div>
      <p className="muted small">
        Content Passport · cryptographic record of how this media was made.
      </p>

      <div className="grid two mt-5.5">
        <div className="card">
          <AssetView job={job} />
          <div className="row mt-4">
            <a className="btn small" href={api.downloadUrl(job.id)}>
              ↓ Download verifiable copy
            </a>
            <Link className="btn small ghost" to="/verify">
              Verify a file
            </Link>
          </div>
          <p className="muted small mt-2.5">
            The verifiable copy has this manifest embedded inside the file. Drop it into the Verify
            page (or run <span className="mono">genblaze verify file.mp4</span>) to confirm origin.
          </p>
        </div>

        <div className="card">
          <div className="section-title mt-0">Provenance</div>
          <div className="kv">
            <span className="k">Run ID</span>
            <span className="mono">{job.run_id || "—"}</span>
          </div>
          <div className="kv">
            <span className="k">Canonical hash</span>
            <span className="mono">{job.manifest_hash || "—"}</span>
          </div>
          <div className="kv">
            <span className="k">Verified</span>
            <span>{job.verified ? "Yes (SHA-256)" : "No"}</span>
          </div>
          <div className="kv">
            <span className="k">Generation cost</span>
            <span>${(job.cost_usd || 0).toFixed(4)}</span>
          </div>
          {job.parent_run_id && (
            <div className="kv">
              <span className="k">Derived from</span>
              <span className="mono">{job.parent_run_id}</span>
            </div>
          )}
          <div className="kv">
            <span className="k">Stored on</span>
            <span>Backblaze B2</span>
          </div>
          {job.manifest_uri && (
            <div className="kv">
              <span className="k">Manifest URI</span>
              <span className="mono">{job.manifest_uri}</span>
            </div>
          )}
        </div>
      </div>

      <div className="section-title">Pipeline lineage</div>
      <div className="grid gap-3">
        {(steps.length ? steps : job.assets).map((s: any, i: number) => (
          <div key={i} className="card p-4">
            <div className="spread">
              <div className="row">
                <span className="tag muted">Step {i}</span>
                <b>{s.provider || s.model || "step"}</b>
                <span className="muted small">{s.model}</span>
              </div>
              <span className="tag muted">{String(s.modality || s.media_type || "")}</span>
            </div>
            {(s.assets?.[0]?.sha256 || s.sha256) && (
              <div className="mono muted mt-2.5">sha256: {s.assets?.[0]?.sha256 || s.sha256}</div>
            )}
          </div>
        ))}
      </div>

      {job.plan && (
        <>
          <div className="section-title">Generated prompts</div>
          <div className="card">
            <div className="kv">
              <span className="k">Image</span>
              <span className="small">{job.plan.image_prompt}</span>
            </div>
            <div className="kv">
              <span className="k">Motion</span>
              <span className="small">{job.plan.video_prompt}</span>
            </div>
            <div className="kv">
              <span className="k">Voiceover</span>
              <span className="small">{job.plan.voiceover}</span>
            </div>
          </div>
        </>
      )}

      {job.manifest && (
        <>
          <div className="section-title spread">
            <span>Raw manifest</span>
            <button className="btn small ghost" onClick={() => setShowJson((v) => !v)}>
              {showJson ? "Hide" : "Show JSON"}
            </button>
          </div>
          {showJson && (
            <pre className="card mono max-h-105 overflow-auto">
              {JSON.stringify(job.manifest, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}
