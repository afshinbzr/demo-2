import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { api } from "../api";
import type { ExecutiveDashboard } from "../types";

const ASSURANCE_COLORS: Record<string, string> = {
  audit: "var(--status-good)",
  review: "var(--series-1)",
  compilation: "#c98500",
  none: "var(--status-critical)",
  unknown: "var(--text-muted)",
};

const ASSURANCE_LABELS: Record<string, string> = {
  audit: "Audit",
  review: "Review",
  compilation: "Compilation",
  none: "Unaudited",
  unknown: "Unknown",
};

const PERIOD_TYPE_LABELS: Record<string, string> = {
  single_period: "Single period",
  multi_year: "Multi-year",
  unknown: "Unknown",
};

function scoreClass(score: number | null): string {
  if (score === null) return "";
  if (score >= 80) return "good";
  if (score >= 60) return "warning";
  return "critical";
}

function GenericTooltip({ active, payload, labelKey, valueLabel }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "0.5rem 0.75rem",
        fontSize: "0.8rem",
      }}
    >
      <div style={{ fontWeight: 700 }}>{p[labelKey]}</div>
      {p.uploaded_at && <div className="muted">{new Date(p.uploaded_at).toLocaleString()}</div>}
      <div>
        {valueLabel}: {payload[0].value}
      </div>
    </div>
  );
}

export default function ExecutiveOverview() {
  const [data, setData] = useState<ExecutiveDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    async function load() {
      try {
        const d = await api.get<ExecutiveDashboard>("/api/dashboard/executive");
        if (!stopped) {
          setData(d);
          setError(null);
        }
      } catch (e) {
        // Only surface an error before the first successful load - see Dashboard.
        if (!stopped) setError((e as Error).message || "Could not load the overview.");
      }
    }
    load();
    const t = setInterval(load, 10000);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, []);

  if (!data) {
    return (
      <div className="page">
        {error ? (
          <div className="card" style={{ borderColor: "var(--status-critical)" }}>
            <strong>Could not load the executive overview.</strong>
            <p className="muted" style={{ marginBottom: 0 }}>{error}</p>
          </div>
        ) : (
          "Loading executive overview…"
        )}
      </div>
    );
  }

  const assuranceData = Object.entries(data.assurance_level_breakdown).map(([key, count]) => ({
    key,
    label: ASSURANCE_LABELS[key] ?? key,
    count,
  }));
  const periodTypeData = Object.entries(data.period_type_breakdown).map(([key, count]) => ({
    key,
    label: PERIOD_TYPE_LABELS[key] ?? key,
    count,
  }));

  return (
    <div className="page">
      <h1>Executive overview</h1>
      <div className="card" style={{ marginBottom: "1.5rem", borderColor: "var(--series-1)" }}>
        <strong>What this page shows — and doesn't.</strong>
        <p className="muted" style={{ marginBottom: 0 }}>
          These are trends in extraction <em>quality and outcomes</em> over the statements this
          tool has processed — not a measure of the underlying AI model improving itself. The
          extraction model is a fixed, static version of Claude; it does not retrain or "learn"
          from the documents it processes. Movement in these numbers reflects the mix and
          difficulty of documents uploaded (cleaner statements score higher; messy scans, unusual
          formats, or heavy language-mixing score lower) and any prompt/pipeline changes made by
          the engineering team — not model self-improvement.
        </p>
      </div>

      <div className="tile-row">
        <div className="tile">
          <div className="label">Total statements</div>
          <div className="value">{data.total_statements}</div>
        </div>
        <div className="tile">
          <div className="label">Processed</div>
          <div className="value good">{data.processed_count}</div>
        </div>
        <div className="tile">
          <div className="label">Quarantined</div>
          <div className={`value ${data.quarantined_count > 0 ? "warning" : "good"}`}>
            {data.quarantined_count}
          </div>
        </div>
        <div className="tile">
          <div className="label">Errors</div>
          <div className={`value ${data.error_count > 0 ? "critical" : "good"}`}>
            {data.error_count}
          </div>
        </div>
        <div className="tile">
          <div className="label">Avg quality score</div>
          <div className={`value ${scoreClass(data.avg_quality_score)}`}>
            {data.avg_quality_score ?? "—"}
          </div>
        </div>
        <div className="tile">
          <div className="label">Verified quotes (portfolio)</div>
          <div className={`value ${scoreClass(data.citation_verification_rate)}`}>
            {data.citation_verification_rate !== null ? `${data.citation_verification_rate}%` : "—"}
          </div>
          <div className="muted" style={{ fontSize: "0.72rem" }}>
            of {data.total_citations_captured} source quotes captured
          </div>
        </div>
        <div className="tile">
          <div className="label">Quarantine resolution rate</div>
          <div className={`value ${scoreClass(data.quarantine_resolution_rate)}`}>
            {data.quarantine_resolution_rate !== null ? `${data.quarantine_resolution_rate}%` : "—"}
          </div>
          <div className="muted" style={{ fontSize: "0.72rem" }}>
            {data.total_quarantine_items} flags raised total
          </div>
        </div>
      </div>

      <div className="detail-grid" style={{ marginBottom: "1.5rem" }}>
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Quality score trend</div>
          {data.quality_trend.length === 0 ? (
            <p className="muted">No processed statements yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.quality_trend} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--gridline)" }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<GenericTooltip labelKey="label" valueLabel="Quality score" />} />
                <Line type="monotone" dataKey="quality_score" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>
            Citation coverage per statement
          </div>
          {data.quality_trend.length === 0 ? (
            <p className="muted">No processed statements yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.quality_trend} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--gridline)" }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<GenericTooltip labelKey="label" valueLabel="Citation coverage" />} />
                <Line type="monotone" dataKey="citation_coverage_score" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="detail-grid">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Portfolio by assurance level</div>
          {assuranceData.length === 0 ? (
            <p className="muted">No data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={assuranceData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--gridline)" }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<GenericTooltip labelKey="label" valueLabel="Statements" />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {assuranceData.map((entry) => (
                    <Cell key={entry.key} fill={ASSURANCE_COLORS[entry.key] ?? "var(--text-muted)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Portfolio by period coverage</div>
          {periodTypeData.length === 0 ? (
            <p className="muted">No data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={periodTypeData} margin={{ left: -20 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--gridline)" }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<GenericTooltip labelKey="label" valueLabel="Statements" />} />
                <Bar dataKey="count" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
