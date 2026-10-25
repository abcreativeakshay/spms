import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Icon } from "../components/Icon";

const DEMO_USERS = [
  { uid: "demo-admin", role: "Super admin", detail: "all colleges, drives, reports" },
  { uid: "demo-trainer", role: "Trainer", detail: "batch attendance and feedback" },
  { uid: "demo-student-1", role: "Student", detail: "Aarav Sharma, placed-ready" },
  { uid: "demo-student-2", role: "Student", detail: "Diya Patel, at-risk" },
];

export default function Login() {
  const { me, signInWithDevToken, signInWithEmail, firebaseEnabled } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("dev");
  const [uid, setUid] = useState("demo-admin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to="/" replace />;

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "dev") await signInWithDevToken(uid);
      else await signInWithEmail(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-slate-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, #4f46e5 0, transparent 45%), radial-gradient(circle at 80% 70%, #0ea5e9 0, transparent 40%)",
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 text-sm font-extrabold backdrop-blur">
              SP
            </div>
            <div>
              <p className="text-lg font-bold">SPMS</p>
              <p className="text-sm text-slate-300">Student Placement Management</p>
            </div>
          </div>
          <h1 className="mt-16 max-w-lg text-4xl font-extrabold leading-tight">
            From attendance to offer letter, one placement workspace.
          </h1>
          <p className="mt-5 max-w-md text-slate-300">
            Track readiness, run eligibility, manage drives and publish placement
            analytics with college-level isolation built in.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-slate-200">
            {[
              "Live readiness across attendance, assessments and interviews",
              "Transparent drive eligibility with blocking reasons",
              "CSV/PDF reporting for accreditation and management",
              "Audit trail on every placement decision",
            ].map((item) => (
              <li key={item} className="flex items-start gap-3">
                <span className="mt-0.5 rounded-full bg-emerald-400/20 p-1 text-emerald-300">
                  <Icon name="check" className="h-3.5 w-3.5" />
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-400">
          FastAPI · Firebase · React · Tailwind
        </p>
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-extrabold text-white">
                SP
              </div>
              <div>
                <p className="font-bold text-slate-900">SPMS</p>
                <p className="text-xs text-slate-500">Placement management</p>
              </div>
            </div>
          </div>

          <h2 className="text-2xl font-bold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">
            Use your institute account, or a development token for local demos.
          </p>

          <div className="mt-6 flex rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setMode("dev")}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-semibold ${mode === "dev" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
            >
              Development
            </button>
            <button
              type="button"
              onClick={() => setMode("email")}
              disabled={!firebaseEnabled}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-semibold disabled:opacity-40 ${mode === "email" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
            >
              Email & password
            </button>
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {mode === "dev" ? (
              <label className="block">
                <span className="label">User ID or dev token</span>
                <input
                  className="input"
                  value={uid}
                  onChange={(event) => setUid(event.target.value)}
                  placeholder="demo-admin"
                  autoComplete="username"
                />
                <span className="mt-1 block text-xs text-slate-400">
                  Sent as <code>Authorization: Bearer dev:&lt;uid&gt;</code>. Only works with
                  <code> USE_FIREBASE=false</code>.
                </span>
              </label>
            ) : (
              <>
                <label className="block">
                  <span className="label">Email</span>
                  <input
                    type="email"
                    className="input"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    autoComplete="email"
                    required
                  />
                </label>
                <label className="block">
                  <span className="label">Password</span>
                  <input
                    type="password"
                    className="input"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    required
                  />
                </label>
              </>
            )}

            {error ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            ) : null}

            <button type="submit" className="btn-primary w-full" disabled={busy}>
              {busy ? "Signing in…" : "Continue"}
            </button>
          </form>

          {mode === "dev" ? (
            <div className="mt-8">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Demo accounts (<code>SEED_DEMO=true</code>)
              </p>
              <div className="mt-2 grid gap-2">
                {DEMO_USERS.map((user) => (
                  <button
                    key={user.uid}
                    type="button"
                    onClick={() => setUid(user.uid)}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm hover:border-brand-300 hover:bg-brand-50/40"
                  >
                    <span>
                      <span className="font-semibold text-slate-900">{user.role}</span>
                      <span className="ml-2 text-xs text-slate-500">{user.detail}</span>
                    </span>
                    <code className="text-xs text-brand-700">{user.uid}</code>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
