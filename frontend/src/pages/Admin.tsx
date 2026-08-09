import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditLogEntry, DataDictionaryEntry, User } from "../types";
import { hasRole, useAuth } from "../AuthContext";

type Tab = "dictionary" | "audit" | "users";

export default function Admin() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("dictionary");
  const [dictionary, setDictionary] = useState<DataDictionaryEntry[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DataDictionaryEntry[]>("/api/admin/data_dictionary")
      .then(setDictionary)
      .catch((e) => setError((e as Error).message || "Could not load the data dictionary."));
  }, []);

  useEffect(() => {
    setError(null);
    if (tab === "audit") {
      api
        .get<AuditLogEntry[]>("/api/admin/audit_log")
        .then(setAuditLog)
        .catch((e) => setError((e as Error).message || "Could not load the audit log."));
    }
    if (tab === "users" && hasRole(user, "admin")) {
      api
        .get<User[]>("/api/admin/users")
        .then(setUsers)
        .catch((e) => setError((e as Error).message || "Could not load users."));
    }
  }, [tab, user]);

  return (
    <div className="page">
      <h1>Admin</h1>
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem" }}>
        <button className={tab === "dictionary" ? "" : "secondary"} onClick={() => setTab("dictionary")}>
          Data dictionary
        </button>
        <button className={tab === "audit" ? "" : "secondary"} onClick={() => setTab("audit")}>
          Audit log
        </button>
        {hasRole(user, "admin") && (
          <button className={tab === "users" ? "" : "secondary"} onClick={() => setTab("users")}>
            Users
          </button>
        )}
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--status-critical)", marginBottom: "1rem" }}>
          <strong>Something went wrong.</strong>
          <p className="muted" style={{ marginBottom: 0 }}>{error}</p>
        </div>
      )}

      {tab === "dictionary" && (
        <div className="card">
          <p className="muted">
            Canonical field metadata (spec 1.6 — data dictionary): field name, type, description,
            source, and owner for every field the extraction pipeline looks for.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Source</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {dictionary.map((d) => (
                  <tr key={d.field_name}>
                    <td>{d.field_name}</td>
                    <td>{d.type}</td>
                    <td>{d.description}</td>
                    <td>{d.source}</td>
                    <td>{d.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "audit" && (
        <div className="card">
          <p className="muted">
            Every create and update — including each AI extraction run — plus every time a
            Confidential/Restricted record's detail page is opened. Rows for statements above
            your clearance are filtered out.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((a) => (
                  <tr key={a.id}>
                    <td>{new Date(a.timestamp).toLocaleString()}</td>
                    <td>{a.username ?? "—"}</td>
                    <td>{a.action}</td>
                    <td>{a.entity_type}{a.entity_id ? ` #${a.entity_id}` : ""}</td>
                    <td>{a.detail ?? "—"}</td>
                  </tr>
                ))}
                {auditLog.length === 0 && (
                  <tr><td colSpan={5} className="muted">No audit events yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "users" && hasRole(user, "admin") && (
        <div className="card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td><span className="role-badge">{u.role}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
