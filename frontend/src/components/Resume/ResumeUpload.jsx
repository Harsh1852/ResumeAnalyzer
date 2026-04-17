import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getPresignedUrl, uploadToS3, confirmUpload, listUploads, getUpload, deleteUpload, deleteResult } from "../../services/api";

const STATUS_LABELS = {
  PENDING: "Pending",
  UPLOADED: "Uploaded",
  PARSING: "Extracting text…",
  ANALYZING: "AI analyzing…",
  COMPLETE: "Complete",
  FAILED: "Failed",
};
const STATUS_COLORS = {
  PENDING: "#6b7280", UPLOADED: "#6b7280", PARSING: "#d97706",
  ANALYZING: "#2563eb", COMPLETE: "#16a34a", FAILED: "#dc2626",
};

const s = {
  page: { maxWidth: 760, margin: "40px auto", padding: "0 20px" },
  card: { background: "#fff", borderRadius: 12, padding: "32px", boxShadow: "0 2px 12px rgba(0,0,0,.07)", marginBottom: 24 },
  title: { margin: "0 0 20px", fontSize: 22, fontWeight: 700 },
  dropzone: (drag) => ({
    border: `2px dashed ${drag ? "#2563eb" : "#d1d5db"}`,
    borderRadius: 10, padding: "48px 24px", textAlign: "center",
    cursor: "pointer", background: drag ? "#eff6ff" : "#f8fafc",
    transition: "all .2s",
  }),
  btn: { padding: "10px 22px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: "pointer" },
  btnGhost: { padding: "8px 16px", background: "transparent", color: "#2563eb", border: "1px solid #2563eb", borderRadius: 8, fontSize: 14, cursor: "pointer" },
  row: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", borderBottom: "1px solid #f1f5f9" },
  badge: (status) => ({ fontSize: 12, fontWeight: 600, color: STATUS_COLORS[status] || "#6b7280", background: "transparent" }),
  progress: { height: 4, background: "#e5e7eb", borderRadius: 2, overflow: "hidden", marginTop: 8 },
  progressBar: (p) => ({ height: "100%", width: `${p}%`, background: "#2563eb", borderRadius: 2, transition: "width .3s" }),
  err: { color: "#dc2626", fontSize: 13, marginTop: 8 },
};

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

function UploadRow({ upload, onViewReport, onDelete }) {
  const [deleting, setDeleting] = useState(false);
  const done = upload.status === "COMPLETE";
  const failed = upload.status === "FAILED";

  async function handleDelete() {
    if (!window.confirm(`Delete "${upload.fileName}" and its report? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteUpload(upload.uploadId);
      if (upload.resultId) await deleteResult(upload.resultId).catch(() => {});
      onDelete(upload.uploadId);
    } catch {
      alert("Delete failed. Please try again.");
      setDeleting(false);
    }
  }

  return (
    <div style={s.row}>
      <div>
        <div style={{ fontWeight: 500 }}>{upload.fileName}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 3 }}>
          <span style={s.badge(upload.status)}>{STATUS_LABELS[upload.status] || upload.status}</span>
          {upload.createdAt && (
            <span style={{ fontSize: 12, color: "#9ca3af" }}>{timeAgo(upload.createdAt)}</span>
          )}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {done && (
          <button style={s.btn} onClick={() => onViewReport(upload.resultId)}>View Report</button>
        )}
        {failed && <span style={{ color: "#dc2626", fontSize: 13 }}>Processing failed</span>}
        {!done && !failed && (
          <span style={{ fontSize: 13, color: "#6b7280" }}>Processing…</span>
        )}
        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{ padding: "7px 14px", background: "none", border: "1px solid #fca5a5", color: "#dc2626", borderRadius: 8, fontSize: 13, cursor: deleting ? "default" : "pointer", opacity: deleting ? 0.6 : 1 }}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </div>
    </div>
  );
}

export default function ResumeUpload() {
  const navigate = useNavigate();
  const fileRef = useRef();
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [uploads, setUploads] = useState([]);
  const [pollingIds, setPollingIds] = useState(new Set());

  useEffect(() => {
    loadUploads();
  }, []);

  async function loadUploads() {
    try {
      const data = await listUploads();
      setUploads(data.uploads || []);
      // Poll any in-progress uploads
      const inProgress = (data.uploads || []).filter(
        (u) => !["COMPLETE", "FAILED"].includes(u.status)
      );
      inProgress.forEach((u) => startPolling(u.uploadId));
    } catch (e) {
      console.error("Failed to load uploads", e);
    }
  }

  function startPolling(uploadId) {
    if (pollingIds.has(uploadId)) return;
    setPollingIds((prev) => new Set([...prev, uploadId]));
    const interval = setInterval(async () => {
      try {
        const upload = await getUpload(uploadId);
        setUploads((prev) => prev.map((u) => (u.uploadId === uploadId ? upload : u)));
        if (["COMPLETE", "FAILED"].includes(upload.status)) {
          clearInterval(interval);
          setPollingIds((prev) => { const n = new Set(prev); n.delete(uploadId); return n; });
        }
      } catch { clearInterval(interval); }
    }, 4000);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) validateAndSet(file);
  }

  function validateAndSet(file) {
    setError("");
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "png", "jpg", "jpeg"].includes(ext)) {
      setError("Only PDF, PNG, JPG files are supported.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10 MB.");
      return;
    }
    setSelectedFile(file);
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadProgress(0);
    setError("");
    try {
      // Step 1: Get presigned URL
      const { uploadId, presignedUrl } = await getPresignedUrl(selectedFile.name, selectedFile.type);
      setUploadProgress(20);

      // Step 2: PUT directly to S3
      await uploadToS3(presignedUrl, selectedFile);
      setUploadProgress(70);

      // Step 3: Confirm upload
      await confirmUpload(uploadId);
      setUploadProgress(100);

      setSelectedFile(null);
      setUploading(false);
      setUploadProgress(0);

      await loadUploads();
      startPolling(uploadId);
    } catch (err) {
      setError(err.response?.data?.error || "Upload failed. Please try again.");
      setUploading(false);
      setUploadProgress(0);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h2 style={s.title}>Upload Resume</h2>
        <div
          style={s.dropzone(dragging)}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current.click()}
        >
          <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" style={{ display: "none" }}
            onChange={(e) => e.target.files[0] && validateAndSet(e.target.files[0])} />
          {selectedFile ? (
            <div>
              <div style={{ fontSize: 16, fontWeight: 500 }}>{selectedFile.name}</div>
              <div style={{ color: "#6b7280", fontSize: 13, marginTop: 4 }}>
                {(selectedFile.size / 1024).toFixed(1)} KB
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 36 }}>📄</div>
              <div style={{ fontWeight: 500, marginTop: 8 }}>Drop your resume here</div>
              <div style={{ color: "#6b7280", fontSize: 13, marginTop: 4 }}>PDF, PNG, JPG — max 10 MB</div>
            </div>
          )}
        </div>

        {error && <p style={s.err}>{error}</p>}

        {uploading && (
          <div style={s.progress}>
            <div style={s.progressBar(uploadProgress)} />
          </div>
        )}

        {selectedFile && !uploading && (
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <button style={s.btn} onClick={handleUpload}>Analyze Resume</button>
            <button style={s.btnGhost} onClick={() => setSelectedFile(null)}>Cancel</button>
          </div>
        )}
      </div>

      {uploads.length > 0 && (
        <div style={s.card}>
          <h2 style={s.title}>Your Resumes</h2>
          {uploads.map((u) => (
            <UploadRow
            key={u.uploadId}
            upload={u}
            onViewReport={(id) => navigate(`/results/${id}`)}
            onDelete={(id) => setUploads((prev) => prev.filter((x) => x.uploadId !== id))}
          />
          ))}
        </div>
      )}
    </div>
  );
}
