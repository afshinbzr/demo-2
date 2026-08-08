import { Fragment, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { LineItem, Ratio, StatementDetail as StatementDetailType } from "../types";
import StatusPill from "../components/StatusPill";
import ClassificationPill from "../components/ClassificationPill";
import { hasRole, useAuth } from "../AuthContext";
import { ASSURANCE_STANDARDS } from "../assuranceStandards";

function formatValue(li: LineItem): string {
  if (li.value === null) return "—";
  const formatted = Math.abs(li.value) >= 1000 ? li.value.toLocaleString() : li.value.toString();
  return `${formatted}${li.unit ? " " + li.unit : ""}`;
}

function formatRatioValue(r: Ratio): string {
  if (r.value === null) return "n/a";
  if (r.unit === "percent") return `${r.value}%`;
  if (r.unit === "currency") return r.value.toLocaleString();
  return r.value.toString();
}

const RATIO_CATEGORY_LABELS: Record<string, string> = {
  liquidity: "Liquidity",
  leverage: "Leverage / Solvency",
  profitability: "Profitability",
  coverage: "Coverage",
};
const RATIO_CATEGORY_ORDER = ["liquidity", "leverage", "profitability", "coverage"];

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

      <div className="badge-row">
        <div className={`info-badge assurance-${statement.assurance_level ?? "unknown"}`}>
          <div className="label">Assurance / Engagement Level</div>
          <div className="headline">
            {ASSURANCE_STANDARDS[statement.assurance_level ?? "unknown"]?.label ?? "Unknown"}
          </div>
          <div className="muted">
            {statement.assurance_standard && statement.assurance_standard !== "n/a"
              ? statement.assurance_standard
              : ASSURANCE_STANDARDS[statement.assurance_level ?? "unknown"]?.standard}
          </div>
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            {ASSURANCE_STANDARDS[statement.assurance_level ?? "unknown"]?.description}
          </p>
          {statement.assurance_quote && (
            <div className="citation-box">
              <div className={statement.assurance_verified ? "confidence-high" : "confidence-medium"}>
                {statement.assurance_verified
                  ? `✓ Verified — Page ${statement.assurance_quote_page}`
                  : "⚠ Unverified — AI-reported, page unknown"}
              </div>
              <div className="quote">"{statement.assurance_quote}"</div>
            </div>
          )}
        </div>

        <div className="info-badge">
          <div className="label">Period Coverage</div>
          <div className="headline">
            {statement.period_type === "multi_year"
              ? "Multi-year / comparative"
              : statement.period_type === "single_period"
              ? "Single period"
              : "Unknown"}
          </div>
          <div className="muted">{statement.periods_covered ?? "Periods not identified"}</div>
        </div>
      </div>

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

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <div className="section-title" style={{ marginTop: 0 }}>Credit analysis ratios</div>
        <p className="muted">
          Standard commercial-lending ratios computed from the extracted figures above (most
          recent period). These are general, widely-used lending ratios — not a reproduction of
          any lender's actual proprietary underwriting scorecard. Thresholds are common rules of
          thumb and vary a lot by industry and facility type in real underwriting.
        </p>
        {statement.ratios.length === 0 ? (
          <p className="muted">No ratios could be computed — not enough line items extracted.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Ratio</th>
                <th>Value</th>
                <th>Formula</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {RATIO_CATEGORY_ORDER.map((cat) => {
                const items = statement.ratios.filter((r) => r.category === cat);
                if (items.length === 0) return null;
                return (
                  <Fragment key={cat}>
                    <tr className="ratio-category-header">
                      <td colSpan={4}>{RATIO_CATEGORY_LABELS[cat]}</td>
                    </tr>
                    {items.map((r) => (
                      <tr key={r.key}>
                        <td>{r.label}</td>
                        <td className={r.flag ? `flag-${r.flag}` : ""}>{formatRatioValue(r)}</td>
                        <td className="muted">{r.formula}</td>
                        <td className="muted">{r.note}</td>
                      </tr>
                    ))}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {statement.detailed_summary && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div className="section-title" style={{ marginTop: 0 }}>
            Detailed summary — for evaluation, audit &amp; decision making
          </div>
          <div className="summary-prose">
            {statement.detailed_summary.split(/\n{2,}/).map((para, i) => (
              <p key={i}>{para}</p>
            ))}
          </div>
        </div>
      )}

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
