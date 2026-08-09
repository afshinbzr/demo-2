import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../AuthContext";

interface DemoUser {
  username: string;
  role: string;
}

interface DemoUsersResponse {
  users: DemoUser[];
  upload_password_required: boolean;
}

export default function Login() {
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState<DemoUser | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get<DemoUsersResponse>("/api/auth/demo_users")
      .then((d) => {
        setDemoUsers(d.users);
        setPasswordRequired(d.upload_password_required);
        setLoadError(null);
      })
      .catch(() => setLoadError("Could not reach the server. Is the backend running?"));
  }, []);

  useEffect(() => {
    if (user) navigate("/");
  }, [user, navigate]);

  async function doLogin(username: string, pw?: string) {
    setError(null);
    setBusy(true);
    try {
      await login(username, pw);
      navigate("/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError("Incorrect password for this role.");
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  function pick(u: DemoUser) {
    // Only stop for a password when one is actually enforced server-side -
    // otherwise the prompt would accept any input, which reads as broken.
    if (u.role === "viewer" || !passwordRequired) {
      doLogin(u.username);
    } else {
      setError(null);
      setPassword("");
      setPending(u);
    }
  }

  return (
    <div className="login-shell">
      <div className="card login-card">
        <span className="brand-logo" style={{ marginBottom: "1rem" }}>
          <img src="/dc-logo-white.svg" alt="" />
        </span>
        <h1 style={{ fontSize: "1.2rem" }}>Sign in</h1>
        <p className="muted">
          Demo authentication — pick a role. In a real deployment this would be replaced
          with your organization's SSO/identity provider.
        </p>

        {loadError && <p style={{ color: "var(--status-critical)" }}>{loadError}</p>}

        {!pending ? (
          <>
            <div className="section-title">Demo users</div>
            {demoUsers.map((u) => (
              <button
                key={u.username}
                type="button"
                className="demo-user"
                disabled={busy}
                onClick={() => pick(u)}
              >
                <span>{u.username}</span>
                <span className="role-badge">{u.role}</span>
              </button>
            ))}
            {demoUsers.length === 0 && !loadError && <p className="muted">Loading users…</p>}
          </>
        ) : (
          <>
            <div className="section-title">
              {pending.username} <span className="role-badge">{pending.role}</span>
            </div>
            <p className="muted">
              This role can upload and edit data, which can trigger a billed AI request —
              enter the shared team password to continue.
            </p>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <label htmlFor="team-password" className="visually-hidden">
                Team password
              </label>
              <input
                id="team-password"
                type="password"
                autoFocus
                placeholder="Team password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") doLogin(pending.username, password);
                }}
              />
              <button disabled={busy} onClick={() => doLogin(pending.username, password)}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </div>
            <button
              className="secondary"
              style={{ marginTop: "0.75rem" }}
              onClick={() => setPending(null)}
            >
              Back
            </button>
          </>
        )}

        {error && <p style={{ color: "var(--status-critical)" }}>{error}</p>}
      </div>
    </div>
  );
}
