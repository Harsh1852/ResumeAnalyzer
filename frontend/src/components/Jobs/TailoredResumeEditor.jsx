import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import MDEditor from "@uiw/react-md-editor";
import html2pdf from "html2pdf.js";
import { getTailoredResume, saveTailoredResume } from "../../services/api";

const s = {
  page: { maxWidth: 1100, margin: "28px auto", padding: "0 20px 60px" },
  bar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 18,
  },
  back: {
    background: "none", border: "none", color: "#2563eb", cursor: "pointer",
    fontSize: 14, padding: 0, fontWeight: 500,
  },
  btnPrimary: {
    background: "linear-gradient(135deg,#2563eb,#1d4ed8)", color: "#fff",
    border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 2px 8px rgba(37,99,235,.25)",
  },
  btnOutline: {
    background: "#fff", color: "#2563eb", border: "1.5px solid #2563eb",
    borderRadius: 10, padding: "9px 18px", fontSize: 13, fontWeight: 600,
    cursor: "pointer",
  },
  meta: {
    display: "flex", gap: 14, alignItems: "center",
    background: "#fff", padding: "14px 20px", borderRadius: 12,
    border: "1px solid #eef1f5", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,.04)",
  },
  metaItem: { fontSize: 12, color: "#64748b", fontWeight: 500 },
  metaStrong: { color: "#0f172a", fontWeight: 700 },
  editorCard: {
    background: "#fff", borderRadius: 14, padding: 16,
    border: "1px solid #eef1f5", boxShadow: "0 2px 14px rgba(15,23,42,.06)",
  },
  status: (color) => ({ fontSize: 12, color, fontWeight: 600 }),
};

export default function TailoredResumeEditor() {
  const { resumeId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [markdown, setMarkdown] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const printRef = useRef();

  useEffect(() => {
    getTailoredResume(resumeId)
      .then((d) => { setDoc(d); setMarkdown(d.markdown || ""); })
      .catch(() => setError("Could not load this tailored resume."));
  }, [resumeId]);

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await saveTailoredResume(resumeId, markdown);
      setDoc(updated);
      setSavedAt(new Date());
    } catch {
      setError("Save failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleDownload() {
    if (!printRef.current) return;
    setDownloading(true);
    html2pdf().set({
      margin: 12,
      filename: "tailored-resume.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    }).from(printRef.current).save().finally(() => setDownloading(false));
  }

  if (error && !doc) return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate(-1)}>← Back</button>
      <div style={{ background: "#fee2e2", color: "#b91c1c", padding: 16, borderRadius: 10, marginTop: 16 }}>{error}</div>
    </div>
  );
  if (!doc) return <div style={{ textAlign: "center", padding: 80, color: "#64748b" }}>Loading…</div>;

  const wordCount = markdown.trim().split(/\s+/).filter(Boolean).length;
  const targetWords = doc.targetWords || 500;
  const overBudget = wordCount > targetWords * 1.15;

  return (
    <div style={s.page}>
      <div style={s.bar}>
        <button style={s.back} onClick={() => navigate(-1)}>← Back to job</button>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {savedAt && <span style={s.status("#16a34a")}>✓ Saved</span>}
          <button onClick={handleDownload} disabled={downloading} style={s.btnOutline}>
            {downloading ? "Exporting…" : "Download PDF"}
          </button>
          <button onClick={handleSave} disabled={saving} style={{ ...s.btnPrimary, opacity: saving ? 0.7 : 1 }}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>

      <div style={s.meta}>
        <div style={s.metaItem}>
          Words: <span style={{ ...s.metaStrong, color: overBudget ? "#dc2626" : "#0f172a" }}>{wordCount}</span>
          <span style={{ color: "#94a3b8", marginLeft: 6 }}>/ {targetWords} target</span>
        </div>
        <div style={{ width: 1, height: 14, background: "#e2e8f0" }} />
        <div style={s.metaItem}>Single-page goal · stay close to target for best fit.</div>
        {error && <div style={{ ...s.status("#dc2626"), marginLeft: "auto" }}>{error}</div>}
      </div>

      <div style={s.editorCard} data-color-mode="light">
        <MDEditor
          value={markdown}
          onChange={(v) => setMarkdown(v || "")}
          height={640}
          preview="live"
          textareaProps={{ placeholder: "Your tailored resume in markdown…" }}
        />
      </div>

      {/* Off-screen print target — renders just the markdown preview for PDF export */}
      <div ref={printRef} style={{ position: "absolute", left: -9999, top: 0, width: 800, padding: 24, background: "#fff" }}>
        <div data-color-mode="light">
          <MDEditor.Markdown source={markdown} style={{ background: "#fff", color: "#0f172a" }} />
        </div>
      </div>
    </div>
  );
}
