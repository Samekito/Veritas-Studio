import { useRef, useState } from "react";
import { useVerify } from "../services/jobsService";

type Result = {
  found: boolean;
  verified: boolean;
  canonical_hash?: string;
  manifest?: any;
  reason?: string;
};

export default function Verify() {
  const [over, setOver] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [name, setName] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const verify = useVerify();
  const busy = verify.isPending;

  function handle(file: File) {
    setName(file.name);
    setResult(null);
    verify.mutate(file, {
      onSuccess: (r) => setResult(r),
      onError: (e) => setResult({ found: false, verified: false, reason: (e as Error).message }),
    });
  }

  return (
    <div className="container">
      <h1 className="text-3xl tracking-[-0.5px]">Verify provenance</h1>
      <p className="muted">
        Drop any media file. If it carries a Genblaze Content Passport, we’ll extract it and
        cryptographically verify it, no account, no trust required.
      </p>

      <div
        className={`drop mt-5 ${over ? "over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) handle(f);
        }}
      >
        <input
          ref={input}
          type="file"
          hidden
          accept="video/mp4,image/png,image/jpeg,audio/mpeg,audio/wav,.mp4,.png,.jpg,.mp3,.wav"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handle(f);
          }}
        />
        {busy ? (
          <div className="row justify-center">
            <span className="spinner" /> Verifying {name}…
          </div>
        ) : (
          <>
            <div className="text-[17px] font-semibold">Drop a file here, or click to browse</div>
            <div className="muted small mt-1.5">
              Tip: download a “verifiable copy” from any Content Passport to try it.
            </div>
          </>
        )}
      </div>

      {result && (
        <div className="card mt-5.5">
          {result.found && result.verified ? (
            <span className="tag good px-3.5 py-2 text-[15px]">
              ✓ Authentic — manifest verified
            </span>
          ) : result.found ? (
            <span className="tag warn px-3.5 py-2 text-[15px]">
              ⚠ Manifest found but failed verification
            </span>
          ) : (
            <span className="tag bad px-3.5 py-2 text-[15px]">✕ No provenance found</span>
          )}

          {result.reason && <p className="muted small mt-3">{result.reason}</p>}
          {result.canonical_hash && (
            <div className="kv mt-3">
              <span className="k">Canonical hash</span>
              <span className="mono">{result.canonical_hash}</span>
            </div>
          )}
          {result.manifest && (
            <pre className="mono mt-3.5 max-h-90 overflow-auto">
              {JSON.stringify(result.manifest, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
