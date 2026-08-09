import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { StatementListItem } from "../types";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../AuthContext";

// Mirrors VISIBLE_CLASSIFICATIONS in backend/app/routers/statements.py. The
// backend is the enforcing side (it 403s); this just avoids offering an option
// that would be rejected.
const CLASSIFICATION_OPTIONS: Record<string, string[]> = {
  viewer: ["Public", "Internal"],
  editor: ["Public", "Internal"],
  steward: ["Public", "Internal", "Confidential"],
  admin: ["Public", "Internal", "Confidential", "Restricted"],
};

export default function Upload() {
  const { user } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [classification, setClassification] = useState("Internal");
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [tracked, setTracked] = useState<StatementListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const options = CLASSIFICATION_OPTIONS[user?.role ?? "editor"] ?? ["Public", "Internal"];

  function addFiles(list: FileList | null) {
    if (!list) return;
    const all = Array.from(list);
    const pdfs = all.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length < all.length) {
      setError("Only PDF files can be uploaded — non-PDF files were ignored.");
    }
    setFiles((prev) => [...prev, ...pdfs]);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    addFiles(e.dataTransfer.files);
  }, []);

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function submit() {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    try {
      const res = await api.postForm<{ statement_ids: number[] }>(
        `/api/statements/upload?classification=${encodeURIComponent(classification)}`,
        form
      );
      const list = await api.get<StatementListItem[]>("/api/statements");
      setTracked(list.filter((s) => res.statement_ids.includes(s.id)));
      setFiles([]);
    } catch (e) {
      setError((e as Error).message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    if (tracked.length === 0) return;
    const hasPending = tracked.some((s) => s.status === "processing");
    if (!hasPending) return;
    const t = setInterval(async () => {
      try {
        const list = await api.get<StatementListItem[]>("/api/statements");
        setTracked((prev) => list.filter((s) => prev.some((p) => p.id === s.id)));
      } catch {
        // Transient poll failure - keep the last known rows on screen and retry.
      }
    }, 2000);
    return () => clearInterval(t);
  }, [tracked]);

  return (
    <div className="page">
      <h1>Upload financial statements</h1>
      <div className="card">
        <div style={{ marginBottom: "1rem" }}>
          <label className="muted" htmlFor="classification">
            Classification for this batch&nbsp;
          </label>
          <select
            id="classification"
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
          >
            {options.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div
          className={`dropzone ${dragActive ? "active" : ""}`}
          role="button"
          tabIndex={0}
          aria-label="Choose PDF financial statements to upload"
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
        >
          <p>Drag &amp; drop PDF financial statements here, or click to browse.</p>
          <p className="muted">Single or bulk upload supported.</p>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            multiple
            style={{ display: "none" }}
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {error && (
          <p style={{ color: "var(--status-critical)", marginBottom: 0 }} role="alert">
            {error}
          </p>
        )}

        {files.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <div className="section-title">
              Ready to upload ({files.length} {files.length === 1 ? "file" : "files"})
            </div>
            <ul className="file-list">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`}>
                  <span>{f.name}</span>
                  <button
                    className="secondary link-button"
                    onClick={() => removeFile(i)}
                    aria-label={`Remove ${f.name}`}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <button onClick={submit} disabled={uploading}>
              {uploading
                ? "Uploading…"
                : `Upload ${files.length} ${files.length === 1 ? "file" : "files"}`}
            </button>
          </div>
        )}
      </div>

      {tracked.length > 0 && (
        <div className="card" style={{ marginTop: "1.25rem" }}>
          <div className="section-title">Processing</div>
          <p className="muted">
            Extraction runs in the background and can take a minute or two per statement.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Status</th>
                  <th>Quality score</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {tracked.map((s) => (
                  <tr key={s.id}>
                    <td>{s.filename}</td>
                    <td>
                      <StatusPill status={s.status} />
                    </td>
                    <td>{s.quality_score ?? "—"}</td>
                    <td>
                      {s.status !== "processing" && <Link to={`/statements/${s.id}`}>View</Link>}
                    </td>
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
