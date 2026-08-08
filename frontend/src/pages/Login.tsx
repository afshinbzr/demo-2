import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../AuthContext";

interface DemoUser {
  username: string;
  role: string;
}

export default function Login() {
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [pending, setPending] = useState<DemoUser | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get<DemoUser[]>("/api/auth/demo_users").then(setDemoUsers).catch(() => {});
  }, []);

  useEffect(() => {
    if (user) navigate("/");
  }, [user, navigate]);

  async function doLogin(username: string, pw?: string) {
    setError(null);
    try {
      await login(username, pw);
      navigate("/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError("Incorrect password for this role.");
      } else {
        setError("Login failed.");
      }
    }
  }

  function pick(u: DemoUser) {
    if (u.role === "viewer") {
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
        <h1 style={{ fontSize: "1.2rem" }}>Sign in</h1>
        <p className="muted">
          Demo authentication — pick a role. In a real deployment this would be replaced
          with your organization's SSO/identity provider.
        </p>

        {!pending ? (
          <>
            <div className="section-title">Demo users</div>
            {demoUsers.map((u) => (
              <div key={u.username} className="demo-user" onClick={() => pick(u)}>
                <span>{u.username}</span>
                <span className="role-badge">{u.role}</span>
              </div>
            ))}
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
              <input
                type="password"
                autoFocus
                placeholder="Team password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") doLogin(pending.username, password);
                }}
              />
              <button onClick={() => doLogin(pending.username, password)}>Sign in</button>
            </div>
            <button className="secondary" style={{ marginTop: "0.75rem" }} onClick={() => setPending(null)}>
              Back
            </button>
          </>
        )}

        {error && <p style={{ color: "var(--status-critical)" }}>{error}</p>}
      </div>
    </div>
  );
}
