import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { api } from "../api";
import type { DashboardMetrics } from "../types";
import StatusPill from "../components/StatusPill";
import ClassificationPill from "../components/ClassificationPill";

function scoreClass(score: number | null): string {
  if (score === null) return "";
  if (score >= 80) return "good";
  if (score >= 60) return "warning";
  return "critical";
}

function TrendTooltip({ active, payload }: any) {
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
      <div style={{ fontWeight: 700 }}>{p.label}</div>
      <div className="muted">{new Date(p.uploaded_at).toLocaleString()}</div>
      <div>Quality score: {p.score}</div>
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);

  useEffect(() => {
    let stopped = false;
    async function load() {
      try {
        const m = await api.get<DashboardMetrics>("/api/dashboard");
        if (!stopped) setMetrics(m);
      } catch {
        /* ignore transient errors while polling */
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, []);

  if (!metrics) return <div className="page">Loading dashboard…</div>;

  return (
    <div className="page">
      <h1>Live data quality dashboard</h1>

      <div className="tile-row">
        <div className="tile">
          <div className="label">Statements</div>
          <div className="value">{metrics.total_statements}</div>
        </div>
        <div className="tile">
          <div className="label">Avg quality score</div>
          <div className={`value ${scoreClass(metrics.avg_quality_score)}`}>
            {metrics.avg_quality_score ?? "—"}
          </div>
        </div>
        <div className="tile">
          <div className="label">Avg completeness</div>
          <div className={`value ${scoreClass(metrics.avg_completeness_pct)}`}>
            {metrics.avg_completeness_pct !== null ? `${metrics.avg_completeness_pct}%` : "—"}
          </div>
        </div>
        <div className="tile">
          <div className="label">Pending quarantine</div>
          <div className={`value ${metrics.quarantine_pending_count > 0 ? "warning" : "good"}`}>
            {metrics.quarantine_pending_count}
          </div>
        </div>
        <div className="tile">
          <div className="label">Stale records (30d+)</div>
          <div className={`value ${metrics.stale_record_count > 0 ? "warning" : "good"}`}>
            {metrics.stale_record_count}
          </div>
        </div>
        <div className="tile">
          <div className="label">Last audit event</div>
          <div className="value" style={{ fontSize: "1.1rem" }}>
            {metrics.last_audit_at ? new Date(metrics.last_audit_at).toLocaleString() : "—"}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <div className="section-title" style={{ marginTop: 0 }}>Quality score trend (recent uploads)</div>
        {metrics.quality_trend.length === 0 ? (
          <p className="muted">No processed statements yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metrics.quality_trend} margin={{ left: -20 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--gridline)" }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<TrendTooltip />} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="var(--series-1)"
                strokeWidth={2}
                dot={{ r: 3, fill: "var(--series-1)" }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>Recent uploads</div>
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Company</th>
              <th>Period</th>
              <th>Classification</th>
              <th>Status</th>
              <th>Quality</th>
            </tr>
          </thead>
          <tbody>
            {metrics.recent_statements.map((s) => (
              <tr key={s.id}>
                <td><Link to={`/statements/${s.id}`}>{s.filename}</Link></td>
                <td>{s.company_name ?? "—"}</td>
                <td>{s.fiscal_period ?? "—"}</td>
                <td><ClassificationPill classification={s.classification} /></td>
                <td><StatusPill status={s.status} /></td>
                <td>{s.quality_score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
