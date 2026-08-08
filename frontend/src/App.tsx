import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { AuthProvider, useAuth, hasRole } from "./AuthContext";
import type { ReactNode } from "react";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import StatementDetail from "./pages/StatementDetail";
import Quarantine from "./pages/Quarantine";
import Admin from "./pages/Admin";

function Protected({ children, minRole = "viewer" }: { children: ReactNode; minRole?: string }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!hasRole(user, minRole)) return <div className="page">Insufficient permissions for this page.</div>;
  return <>{children}</>;
}

function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
          <span className="brand">📊 Statement Governance</span>
          {user && (
            <nav>
              <NavLink to="/">Dashboard</NavLink>
              {hasRole(user, "editor") && <NavLink to="/upload">Upload</NavLink>}
              {hasRole(user, "steward") && <NavLink to="/quarantine">Quarantine</NavLink>}
              {hasRole(user, "steward") && <NavLink to="/admin">Admin</NavLink>}
            </nav>
          )}
        </div>
        {user && (
          <div className="user-chip">
            {user.username}
            <span className="role-badge">{user.role}</span>
            <button className="secondary" onClick={() => logout()}>
              Log out
            </button>
          </div>
        )}
      </header>
      {children}
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout>
              <Dashboard />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/upload"
        element={
          <Protected minRole="editor">
            <Layout>
              <Upload />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/statements/:id"
        element={
          <Protected>
            <Layout>
              <StatementDetail />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/quarantine"
        element={
          <Protected minRole="steward">
            <Layout>
              <Quarantine />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/admin"
        element={
          <Protected minRole="steward">
            <Layout>
              <Admin />
            </Layout>
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
