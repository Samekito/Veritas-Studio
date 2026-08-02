import { useState } from "react";
import { useAuthStore } from "../stores/useAuthStore";

export default function Login() {
  const login = useAuthStore((s) => s.login);
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(password);
    } catch {
      setErr("Incorrect password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center p-6">
      <form className="card w-95 max-w-full" onSubmit={submit}>
        <div className="row mb-2 gap-2.5">
          <span className="dot" />
          <b className="text-lg">Veritas Admin</b>
        </div>
        <p className="muted small mt-0">
          Super-admin access — operations console for Veritas Studio.
        </p>
        <div className="field mt-3">
          <label>Password</label>
          <input
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter admin password"
          />
        </div>
        <button className="btn w-full" disabled={busy || !password}>
          {busy ? <span className="spinner" /> : null} Sign in
        </button>
        {err && <div className="banner bad mt-3.5">{err}</div>}
      </form>
    </div>
  );
}
