import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { LineItem, StatementDetail as StatementDetailType } from "../types";
import StatusPill from "../components/StatusPill";
import ClassificationPill from "../components/ClassificationPill";
import { hasRole, useAuth } from "../AuthContext";

function formatValue(li: LineItem): string {
  if (li.value === null) return "—";
  const formatted = Math.abs(li.value) >= 1000 ? li.value.toLocaleString() : li.value.toString();
  return `${formatted}${li.unit ? " " + li.unit : ""}`;
}

export default function StatementDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [statement, setStatement] = useState<StatementDetailType | null>(null);
  const [selected, setSelected] = useState<LineItem | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const s = await api.get<StatementDetailType>(`/api/statements/${id}`);
      setStatement(s);
      setError(null);
      if (selected) {
        setSelected(s.line_items.find((li) => li.id === selected.id) ?? null);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function saveCorrection() {
    if (!statement || !selected) return;
    const value = parseFloat(editValue);
    if (Number.isNaN(value)) return;
    setEditing(true);
    try {
      await api.patch(`/api/statements/${statement.id}/line_items/${selected.id}`, { value });
      setSelected(null);
      await load();
    } catch (e) {
      alert("Correction failed: " + (e as Error).message);
    } finally {
      setEditing(false);
    }
  }

  if (error) return <div className="page">Error: {error}</div>;
  if (!statement) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <div className="flex-between">
        <h1 style={{ marginBottom: "0.25rem" }}>{statement.filename}</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <ClassificationPill classification={statement.classification} />
          <StatusPill status={statement.status} />
        </div>
      </div>
      <p className="muted">
        {statement.company_name ?? "Unknown company"} · {statement.statement_type ?? "unknown type"} ·{" "}
        {statement.fiscal_period ?? "unknown period"} · {statement.currency ?? ""}
      </p>

      {statement.status === "error" && (
        <div className="card" style={{ borderColor: "var(--status-critical)" }}>
          <strong>Extraction failed:</strong> {statement.error_detail}
        </div>
      )}

      <div className="tile-row">
        <div className="tile">
          <div className="label">Quality score</div>
          <div className="value">{statement.quality_score ?? "—"}</div>
        </div>
        <div className="tile">
          <div className="label">Completeness</div>
          <div className="value">{statement.completeness_score ?? "—"}</div>
        </div>
        <div className="tile">
          <div className="label">Validity</div>
          <div className="value">{statement.validity_score ?? "—"}</div>
        </div>
        <div className="tile">
          <div className="label">Consistency</div>
          <div className="value">{statement.consistency_score ?? "—"}</div>
        </div>
        <div className="tile">
          <div className="label">Uniqueness</div>
          <div className="value">{statement.uniqueness_score ?? "—"}</div>
        </div>
        <div className="tile">
          <div className="label">Citation coverage (reliability)</div>
          <div className="value">{statement.citation_coverage_score ?? "—"}</div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Extracted line items</div>
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Value</th>
                <th>Period</th>
                <th>Confidence</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {statement.line_items.map((li) => (
                <tr
                  key={li.id}
                  className={`line-item-row ${selected?.id === li.id ? "selected" : ""}`}
                  onClick={() => {
                    setSelected(li);
                    setEditValue(li.value?.toString() ?? "");
                  }}
                >
                  <td>{li.raw_label ?? li.field_name}</td>
                  <td>{formatValue(li)}</td>
                  <td>{li.period ?? "—"}</td>
                  <td className={`confidence-${li.confidence}`}>
                    {li.confidence}
                    {li.is_outlier && <span className="outlier-flag"> ⚠ outlier</span>}
                  </td>
                  <td>v{li.version}</td>
                </tr>
              ))}
              {statement.line_items.length === 0 && (
                <tr><td colSpan={5} className="muted">No line items extracted.</td></tr>
              )}
            </tbody>
          </table>

          {statement.ai_notes && (
            <>
              <div className="section-title">AI notes — judgment calls made during extraction</div>
              <div className="citation-box">
                <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>
                  {statement.ai_notes}
                </pre>
              </div>
            </>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Cross-reference</div>
          {!selected ? (
            <p className="muted">Select a line item to see its source quote and page number.</p>
          ) : (
            <div>
              <p>
                <strong>{selected.raw_label ?? selected.field_name}</strong>: {formatValue(selected)}
              </p>
              {selected.citations.length === 0 ? (
                <p className="muted">
                  No verified citation was attached to this value by the AI — treat with lower
                  confidence and verify manually against the source PDF.
                </p>
              ) : (
                selected.citations.map((c) => (
                  <div key={c.id} className="citation-box">
                    <div className={c.verified ? "confidence-high" : "confidence-medium"}>
                      {c.verified
                        ? `✓ Verified — Page ${c.page_number}`
                        : "⚠ Unverified — AI-reported quote, page unknown (search the PDF to confirm)"}
                    </div>
                    <div className="quote">"{c.cited_text}"</div>
                  </div>
                ))
              )}

              {hasRole(user, "editor") && (
                <>
                  <div className="section-title">Correct this value</div>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <input
                      type="number"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                    />
                    <button onClick={saveCorrection} disabled={editing}>
                      {editing ? "Saving…" : "Save correction"}
                    </button>
                  </div>
                  <p className="muted">
                    Saving creates a new version (v{selected.version + 1}) — the AI-extracted
                    value is kept in history, never overwritten.
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
