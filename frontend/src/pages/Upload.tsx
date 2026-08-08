import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { StatementListItem } from "../types";
import StatusPill from "../components/StatusPill";

export default function Upload() {
  const [files, setFiles] = useState<File[]>([]);
  const [classification, setClassification] = useState("Internal");
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [tracked, setTracked] = useState<StatementListItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const pdfs = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    setFiles((prev) => [...prev, ...pdfs]);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    addFiles(e.dataTransfer.files);
  }, []);

  async function submit() {
    if (files.length === 0) return;
    setUploading(true);
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
      alert("Upload failed: " + (e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    if (tracked.length === 0) return;
    const hasPending = tracked.some((s) => s.status === "processing");
    if (!hasPending) return;
    const t = setInterval(async () => {
      const list = await api.get<StatementListItem[]>("/api/statements");
      setTracked((prev) => list.filter((s) => prev.some((p) => p.id === s.id)));
    }, 2000);
    return () => clearInterval(t);
  }, [tracked]);

  return (
    <div className="page">
      <h1>Upload financial statements</h1>
      <div className="card">
        <div style={{ marginBottom: "1rem" }}>
          <label className="muted">Classification for this batch&nbsp;</label>
          <select value={classification} onChange={(e) => setClassification(e.target.value)}>
            <option>Public</option>
            <option>Internal</option>
            <option>Confidential</option>
            <option>Restricted</option>
          </select>
        </div>

        <div
          className={`dropzone ${dragActive ? "active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
        >
          <p>Drag & drop PDF financial statements here, or click to browse.</p>
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

        {files.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <div className="section-title">Ready to upload ({files.length})</div>
            <ul>
              {files.map((f, i) => (
                <li key={i}>{f.name}</li>
              ))}
            </ul>
            <button onClick={submit} disabled={uploading}>
              {uploading ? "Uploading…" : `Upload ${files.length} file(s)`}
            </button>
          </div>
        )}
      </div>

      {tracked.length > 0 && (
        <div className="card" style={{ marginTop: "1.25rem" }}>
          <div className="section-title">Processing</div>
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
                  <td><StatusPill status={s.status} /></td>
                  <td>{s.quality_score ?? "—"}</td>
                  <td>
                    {s.status !== "processing" && <Link to={`/statements/${s.id}`}>View</Link>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
