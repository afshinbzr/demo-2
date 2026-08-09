import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { QuarantineItem, StatementListItem } from "../types";

/** Turn a machine reason code ("missing_required_field") into a readable label
 * for the queue. The raw code is still what's stored and audited. */
function humanizeReasonCode(code: string): string {
  return code.replace(/_/g, " ");
}

export default function Quarantine() {
  const [items, setItems] = useState<QuarantineItem[]>([]);
  const [statements, setStatements] = useState<Record<number, StatementListItem>>({});
  const [filter, setFilter] = useState("pending");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [q, s] = await Promise.all([
        api.get<QuarantineItem[]>(`/api/quarantine?status_filter=${filter}`),
        api.get<StatementListItem[]>("/api/statements"),
      ]);
      setItems(q);
      setStatements(Object.fromEntries(s.map((st) => [st.id, st])));
      setError(null);
    } catch (e) {
      setError((e as Error).message || "Could not load the quarantine queue.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function resolve(item: QuarantineItem, resolution: "approved" | "corrected" | "rejected") {
    setBusyId(item.id);
    try {
      await api.post(`/api/quarantine/${item.id}/resolve`, {
        resolution,
        note: notes[item.id] || null,
        corrected_value:
          resolution === "corrected" && corrections[item.id]
            ? parseFloat(corrections[item.id])
            : null,
      });
      await load();
    } catch (e) {
      setError("Could not resolve that item: " + (e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page">
      <div className="flex-between">
        <h1>Quarantine review queue</h1>
        <select
          aria-label="Filter quarantine items by status"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="pending">Pending</option>
          <option value="resolved">Resolved</option>
          <option value="all">All</option>
        </select>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--status-critical)", marginBottom: "1rem" }}>
          <strong>Something went wrong.</strong>
          <p className="muted" style={{ marginBottom: 0 }}>{error}</p>
        </div>
      )}

      {/* Distinguish "still loading" from "genuinely empty" so the page doesn't
          flash "Nothing here." before the first fetch resolves. */}
      {loading && <p className="muted">Loading…</p>}
      {!loading && !error && items.length === 0 && (
        <p className="muted">
          {filter === "pending"
            ? "No pending items — every flag has been reviewed."
            : "Nothing here."}
        </p>
      )}

      {items.map((item) => {
        const st = statements[item.statement_id];
        return (
          <div className="card" key={item.id} style={{ marginBottom: "1rem" }}>
            <div className="flex-between">
              <div>
                <span className="status-pill status-quarantined">
                  {humanizeReasonCode(item.reason_code)}
                </span>{" "}
                {st ? (
                  <Link to={`/statements/${st.id}`}>{st.filename}</Link>
                ) : (
                  `Statement #${item.statement_id}`
                )}
              </div>
              <span className="muted">{new Date(item.created_at).toLocaleString()}</span>
            </div>
            <p>{item.detail}</p>

            {item.status === "pending" ? (
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                <input
                  placeholder="Note (optional)"
                  value={notes[item.id] || ""}
                  onChange={(e) => setNotes({ ...notes, [item.id]: e.target.value })}
                  style={{ flex: 1, minWidth: 160 }}
                />
                {item.line_item_id && (
                  <input
                    type="number"
                    placeholder="Corrected value"
                    style={{ width: 140 }}
                    value={corrections[item.id] || ""}
                    onChange={(e) => setCorrections({ ...corrections, [item.id]: e.target.value })}
                  />
                )}
                <button
                  className="secondary"
                  disabled={busyId === item.id}
                  onClick={() => resolve(item, "approved")}
                >
                  Approve (flag is fine)
                </button>
                {item.line_item_id && (
                  <button
                    disabled={busyId === item.id || !corrections[item.id]}
                    onClick={() => resolve(item, "corrected")}
                  >
                    Apply correction
                  </button>
                )}
                <button
                  className="danger"
                  disabled={busyId === item.id}
                  onClick={() => resolve(item, "rejected")}
                >
                  Reject data
                </button>
              </div>
            ) : (
              <p className="muted">
                {["Resolved", item.resolution_note, item.reviewed_at ? new Date(item.reviewed_at).toLocaleString() : null]
                  .filter(Boolean)
                  .join(" — ")}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
