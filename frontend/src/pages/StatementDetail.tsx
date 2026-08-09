import { Fragment, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { Citation, LineItem, Ratio, StatementDetail as StatementDetailType } from "../types";
import StatusPill from "../components/StatusPill";
import ClassificationPill from "../components/ClassificationPill";
import HoverTooltip from "../components/HoverTooltip";
import { hasRole, useAuth } from "../AuthContext";
import { ASSURANCE_STANDARDS } from "../assuranceStandards";

function formatValue(li: LineItem): string {
  if (li.value === null) return "—";
  const formatted = Math.abs(li.value) >= 1000 ? li.value.toLocaleString() : li.value.toString();
  return `${formatted}${li.unit ? " " + li.unit : ""}`;
}

function CitationTooltipContent({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return <p className="muted" style={{ margin: 0 }}>No source quote captured for this value.</p>;
  }
  return (
    <>
      {citations.map((c) => (
        <div key={c.id} style={{ marginBottom: "0.4rem" }}>
          <div className={`tt-status ${c.verified ? "confidence-high" : "confidence-medium"}`}>
            {c.verified ? `✓ Verified — Page ${c.page_number}` : "⚠ Unverified — AI-reported"}
          </div>
          <div className="tt-quote">"{c.cited_text}"</div>
        </div>
      ))}
    </>
  );
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

const STATEMENT_TYPE_LABELS: Record<string, string> = {
  income_statement: "Income statement",
  balance_sheet: "Balance sheet",
  cash_flow: "Cash flow statement",
  other: "Full statement package",
};

const LANGUAGE_LABELS: Record<string, string> = {
  english: "English",
  french: "French",
  bilingual_en_fr: "Bilingual (English/French)",
  other: "Other language",
  unknown: "Unknown",
};

const SUMMARY_SECTION_META: Record<string, { label: string; icon: string }> = {
  PROFITABILITY_SUMMARY: { label: "Profitability", icon: "📈" },
  LIQUIDITY_SUMMARY: { label: "Liquidity", icon: "💧" },
  LEVERAGE_SUMMARY: { label: "Leverage & Solvency", icon: "⚖️" },
  CASH_FLOW_SUMMARY: { label: "Cash Flow", icon: "💵" },
};

export default function StatementDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [statement, setStatement] = useState<StatementDetailType | null>(null);
  const [selected, setSelected] = useState<LineItem | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

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
    if (Number.isNaN(value)) {
      setCorrectionError("Enter a number before saving.");
      return;
    }
    setEditing(true);
    setCorrectionError(null);
    try {
      await api.patch(`/api/statements/${statement.id}/line_items/${selected.id}`, { value });
      setSelected(null);
      await load();
    } catch (e) {
      setCorrectionError((e as Error).message || "Could not save that correction.");
    } finally {
      setEditing(false);
    }
  }

  if (error) {
    return (
      <div className="page">
        <div className="card" style={{ borderColor: "var(--status-critical)" }}>
          <strong>Could not load this statement.</strong>
          <p className="muted" style={{ marginBottom: 0 }}>{error}</p>
        </div>
      </div>
    );
  }
  if (!statement) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <div className="flex-between">
        <h1 className="statement-title">{statement.filename}</h1>
        <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
          <ClassificationPill classification={statement.classification} />
          <StatusPill status={statement.status} />
        </div>
      </div>
      <p className="muted">
        {/* Built by filtering then joining so a missing field never leaves a
            dangling "·" separator at the end of the line. */}
        {[
          statement.company_name ?? "Unknown company",
          STATEMENT_TYPE_LABELS[statement.statement_type ?? ""] ?? statement.statement_type,
          statement.fiscal_period,
          statement.currency,
        ]
          .filter(Boolean)
          .join(" · ")}
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

        <div className="info-badge">
          <div className="label">Document Format &amp; Language</div>
          <div className="headline">
            {LANGUAGE_LABELS[statement.language_detected ?? "unknown"] ?? "Unknown"}
          </div>
          {statement.structure_note && (
            <p className="muted" style={{ marginTop: "0.4rem" }}>
              <strong>Format:</strong> {statement.structure_note}
            </p>
          )}
          {statement.unit_scale_note && (
            <p
              className={statement.unit_scale_uncertain ? "" : "muted"}
              style={{
                marginTop: "0.4rem",
                color: statement.unit_scale_uncertain ? "var(--status-critical)" : undefined,
                fontWeight: statement.unit_scale_uncertain ? 600 : undefined,
              }}
            >
              <strong>Units:</strong>{" "}
              {/* Strip the prompt's "UNCERTAIN:" sentinel - it drives the styling
                  above, it shouldn't leak into the sentence the user reads. */}
              {statement.unit_scale_note.replace(/^UNCERTAIN:\s*/i, "")}
            </p>
          )}
        </div>
      </div>

      {statement.status === "error" && (
        <div className="card" style={{ borderColor: "var(--status-critical)" }}>
          <strong>Extraction failed.</strong>
          <p className="muted" style={{ marginBottom: 0 }}>
            This statement could not be processed. Re-upload it, or ask an administrator to
            check the server logs.
          </p>
          {/* The raw exception can contain provider/internal detail, so it's
              shown only to admins - everyone else gets the plain message. */}
          {hasRole(user, "admin") && statement.error_detail && (
            <details style={{ marginTop: "0.6rem" }}>
              <summary className="muted" style={{ cursor: "pointer" }}>
                Technical detail (admin only)
              </summary>
              <pre className="error-detail-pre">{statement.error_detail}</pre>
            </details>
          )}
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
          <div className="table-scroll">
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
          </div>
        )}
      </div>

      {Object.keys(statement.summary_sections).length > 0 && (
        <div style={{ marginBottom: "1.5rem" }}>
          <div className="section-title" style={{ marginTop: 0, marginBottom: "0.75rem" }}>
            Detailed summary — for evaluation, audit &amp; decision making
          </div>

          <div className="summary-grid">
            {Object.entries(SUMMARY_SECTION_META).map(([key, meta]) => {
              const text = statement.summary_sections[key];
              if (!text) return null;
              return (
                <div className="card summary-card" key={key}>
                  <div className="summary-card-title">
                    <span>{meta.icon}</span> {meta.label}
                  </div>
                  <p className="summary-card-text">{text}</p>
                </div>
              );
            })}
          </div>

          {statement.summary_sections.RED_FLAGS && (
            <div className="card" style={{ marginTop: "1rem", borderColor: "var(--status-warning)" }}>
              <div className="summary-card-title">🚩 Red Flags / Watch Items</div>
              <ul className="red-flags-list">
                {statement.summary_sections.RED_FLAGS.split("\n")
                  .map((line) => line.replace(/^-\s*/, "").trim())
                  .filter(Boolean)
                  .map((flag, i) => (
                    <li key={i}>{flag}</li>
                  ))}
              </ul>
            </div>
          )}

          {statement.summary_sections.OVERALL_ASSESSMENT && (
            <div className="card" style={{ marginTop: "1rem", borderColor: "var(--series-1)" }}>
              <div className="summary-card-title">✅ Overall Assessment</div>
              <p className="summary-card-text">{statement.summary_sections.OVERALL_ASSESSMENT}</p>
            </div>
          )}
        </div>
      )}

      <div className="detail-grid">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Extracted line items</div>
          <div className="table-scroll">
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
                    <td>
                      <HoverTooltip content={<CitationTooltipContent citations={li.citations} />}>
                        {formatValue(li)}
                      </HoverTooltip>
                    </td>
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
          </div>

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
                    <label htmlFor="corrected-value" className="visually-hidden">
                      Corrected value
                    </label>
                    <input
                      id="corrected-value"
                      type="number"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                    />
                    <button onClick={saveCorrection} disabled={editing}>
                      {editing ? "Saving…" : "Save correction"}
                    </button>
                  </div>
                  {correctionError && (
                    <p style={{ color: "var(--status-critical)" }} role="alert">
                      {correctionError}
                    </p>
                  )}
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
