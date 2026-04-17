import React, { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  getPresignedUrl, uploadToS3, confirmUpload, listUploads, getUpload,
  deleteUpload, deleteResult, getApplicationStats,
} from "../../services/api";

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
  page: { maxWidth: 960, margin: "32px auto", padding: "0 24px 60px" },
  hero: {
    background: "linear-gradient(135deg,#1e3a8a,#2563eb 60%,#3b82f6)",
    borderRadius: 16, padding: "32px 36px", color: "#fff",
    boxShadow: "0 8px 30px rgba(30,58,138,.25)", marginBottom: 24,
    position: "relative", overflow: "hidden",
  },
  heroTitle: { fontSize: 28, fontWeight: 800, margin: 0, letterSpacing: "-.01em", lineHeight: 1.2 },
  heroSub: { fontSize: 15, opacity: 0.9, marginTop: 8, maxWidth: 600, lineHeight: 1.5 },
  heroMeta: { display: "flex", flexWrap: "wrap", gap: 10, marginTop: 18 },
  heroPill: {
    background: "rgba(255,255,255,.18)", color: "#fff",
    padding: "6px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600,
    backdropFilter: "blur(4px)",
  },
  actions: {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 14, marginBottom: 26,
  },
  action: {
    background: "#fff", borderRadius: 12, padding: "18px 20px",
    border: "1px solid #eef1f5", boxShadow: "0 1px 6px rgba(15,23,42,.05)",
    textDecoration: "none", color: "inherit", transition: "all .15s",
    cursor: "pointer", display: "block",
  },
  actionIcon: { fontSize: 24, marginBottom: 10 },
  actionTitle: { fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 },
  actionDesc: { fontSize: 13, color: "#64748b", lineHeight: 1.45 },
  card: {
    background: "#fff", borderRadius: 14, padding: "28px 30px", marginBottom: 22,
    border: "1px solid #eef1f5", boxShadow: "0 2px 14px rgba(15,23,42,.05)",
  },
  cardTitle: { margin: "0 0 18px", fontSize: 18, fontWeight: 700, color: "#0f172a" },
  dropzone: (drag) => ({
    border: `2px dashed ${drag ? "#2563eb" : "#cbd5e1"}`,
    borderRadius: 12, padding: "48px 24px", textAlign: "center",
    cursor: "pointer", background: drag ? "#eff6ff" : "#f8fafc",
    transition: "all .18s",
  }),
  btnPrimary: {
    padding: "11px 22px", background: "linear-gradient(135deg,#2563eb,#1d4ed8)", color: "#fff",
    border: "none", borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: "pointer",
    boxShadow: "0 4px 14px rgba(37,99,235,.3)",
  },
  btnGhost: {
    padding: "10px 20px", background: "transparent", color: "#2563eb",
    border: "1.5px solid #2563eb", borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: "pointer",
  },
  row: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "16px 0", borderBottom: "1px solid #f1f5f9",
  },
  badge: (status) => ({
    fontSize: 12, fontWeight: 700, color: STATUS_COLORS[status] || "#6b7280",
    background: (STATUS_COLORS[status] || "#6b7280") + "15",
    padding: "3px 10px", borderRadius: 20,
  }),
  progress: { height: 4, background: "#e5e7eb", borderRadius: 2, overflow: "hidden", marginTop: 10 },
  progressBar: (p) => ({ height: "100%", width: `${p}%`, background: "#2563eb", borderRadius: 2, transition: "width .3s" }),
  err: { color: "#dc2626", fontSize: 13, marginTop: 10 },
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

function ActionCard({ to, icon, title, desc, accent }) {
  const [hover, setHover] = useState(false);
  return (
    <Link
      to={to}
      style={{
        ...s.action,
        borderLeft: `4px solid ${accent}`,
        ...(hover ? { transform: "translateY(-2px)", boxShadow: "0 8px 24px rgba(15,23,42,.10)" } : null),
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={s.actionIcon}>{icon}</div>
      <div style={s.actionTitle}>{title}</div>
      <div style={s.actionDesc}>{desc}</div>
    </Link>
  );
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
        <div style={{ fontWeight: 600, color: "#0f172a" }}>{upload.fileName}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
          <span style={s.badge(upload.status)}>{STATUS_LABELS[upload.status] || upload.status}</span>
          {upload.createdAt && (
            <span style={{ fontSize: 12, color: "#9ca3af" }}>{timeAgo(upload.createdAt)}</span>
          )}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {done && (
          <button style={s.btnPrimary} onClick={() => onViewReport(upload.resultId)}>View Report</button>
        )}
        {failed && <span style={{ color: "#dc2626", fontSize: 13 }}>Processing failed</span>}
        {!done && !failed && (
          <span style={{ fontSize: 13, color: "#6b7280" }}>Processing…</span>
        )}
        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{ padding: "8px 14px", background: "none", border: "1.5px solid #fca5a5", color: "#dc2626", borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: deleting ? "default" : "pointer", opacity: deleting ? 0.6 : 1 }}
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
  const [stats, setStats] = useState(null);
  const intervalsRef = useRef(new Map());

  useEffect(() => {
    loadUploads();
    getApplicationStats().then(setStats).catch(() => {});
    return () => {
      intervalsRef.current.forEach(clearInterval);
      intervalsRef.current.clear();
    };
  }, []);

  async function loadUploads() {
    try {
      const data = await listUploads();
      setUploads(data.uploads || []);
      (data.uploads || [])
        .filter((u) => !["COMPLETE", "FAILED"].includes(u.status))
        .forEach((u) => startPolling(u.uploadId));
    } catch (e) {
      console.error("Failed to load uploads", e);
    }
  }

  function startPolling(uploadId) {
    if (intervalsRef.current.has(uploadId)) return;
    const interval = setInterval(async () => {
      try {
        const upload = await getUpload(uploadId);
        setUploads((prev) => prev.map((u) => (u.uploadId === uploadId ? upload : u)));
        if (["COMPLETE", "FAILED"].includes(upload.status)) {
          clearInterval(interval);
          intervalsRef.current.delete(uploadId);
        }
      } catch {
        clearInterval(interval);
        intervalsRef.current.delete(uploadId);
      }
    }, 4000);
    intervalsRef.current.set(uploadId, interval);
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
      const { uploadId, presignedUrl } = await getPresignedUrl(selectedFile.name, selectedFile.type);
      setUploadProgress(20);
      await uploadToS3(presignedUrl, selectedFile);
      setUploadProgress(70);
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

  const completedReports = uploads.filter((u) => u.status === "COMPLETE").length;

  return (
    <div style={s.page}>
      {/* Hero */}
      <div style={s.hero}>
        <h1 style={s.heroTitle}>Welcome back 👋</h1>
        <div style={s.heroSub}>
          Upload a resume to get an AI analysis with real job listings, course recommendations, and a one-page tailored resume — then track every application in one place.
        </div>
        <div style={s.heroMeta}>
          <span style={s.heroPill}>📄 {uploads.length} resume{uploads.length !== 1 ? "s" : ""} uploaded</span>
          <span style={s.heroPill}>📊 {completedReports} report{completedReports !== 1 ? "s" : ""} ready</span>
          {stats && <span style={s.heroPill}>📋 {stats.total} application{stats.total !== 1 ? "s" : ""} tracked</span>}
          {stats && stats.active > 0 && <span style={s.heroPill}>⚡ {stats.active} active</span>}
        </div>
      </div>

      {/* Quick actions */}
      <div style={s.actions}>
        <ActionCard
          to="/tracker"
          icon="📋"
          title="Application Tracker"
          desc="Kanban of every job you've applied to, with interview rounds and status timeline."
          accent="#2563eb"
        />
        <ActionCard
          to="/tracker/new"
          icon="➕"
          title="Track a new application"
          desc="Add a job manually — even one you found outside the app."
          accent="#16a34a"
        />
        <ActionCard
          to="/profile"
          icon="⚙️"
          title="Account & settings"
          desc="Update your email, change password, or delete your account."
          accent="#7c3aed"
        />
      </div>

      {/* Upload card */}
      <div style={s.card}>
        <h2 style={s.cardTitle}>Upload a new resume</h2>
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
              <div style={{ fontSize: 16, fontWeight: 600, color: "#0f172a" }}>{selectedFile.name}</div>
              <div style={{ color: "#6b7280", fontSize: 13, marginTop: 4 }}>
                {(selectedFile.size / 1024).toFixed(1)} KB
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 42 }}>📄</div>
              <div style={{ fontWeight: 600, marginTop: 10, color: "#0f172a" }}>Drop your resume here</div>
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
          <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
            <button style={s.btnPrimary} onClick={handleUpload}>Analyze Resume</button>
            <button style={s.btnGhost} onClick={() => setSelectedFile(null)}>Cancel</button>
          </div>
        )}
      </div>

      {/* Uploads list */}
      {uploads.length > 0 && (
        <div style={s.card}>
          <h2 style={s.cardTitle}>Your Resumes</h2>
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
