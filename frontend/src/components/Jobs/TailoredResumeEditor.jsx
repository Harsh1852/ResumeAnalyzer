import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import MDEditor from "@uiw/react-md-editor";
import CodeMirror from "@uiw/react-codemirror";
import { StreamLanguage } from "@codemirror/language";
import { stex } from "@codemirror/legacy-modes/mode/stex";
import { getTailoredResume, saveTailoredResume } from "../../services/api";

const s = {
  page: { maxWidth: 1100, margin: "28px auto", padding: "0 20px 60px" },
  bar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 18, flexWrap: "wrap", gap: 10,
  },
  back: {
    background: "none", border: "none", color: "#b8860b", cursor: "pointer",
    fontSize: 14, padding: 0, fontWeight: 500,
  },
  btnPrimary: {
    background: "linear-gradient(135deg,#b8860b,#d4af37)", color: "#fff",
    border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 2px 10px rgba(184,134,11,.3)",
    letterSpacing: "-0.005em",
  },
  btnOutline: {
    background: "#fff", color: "#b8860b", border: "1.5px solid #b8860b",
    borderRadius: 10, padding: "9px 18px", fontSize: 13, fontWeight: 600,
    cursor: "pointer", textDecoration: "none", display: "inline-block",
  },
  meta: {
    display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap",
    background: "#fff", padding: "14px 20px", borderRadius: 12,
    border: "1px solid #eef1f5", marginBottom: 16, boxShadow: "0 1px 4px rgba(0,0,0,.04)",
  },
  metaItem: { fontSize: 12, color: "#64748b", fontWeight: 500 },
  metaStrong: { color: "#0f172a", fontWeight: 700 },
  formatPill: {
    fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20,
    background: "#eff6ff", color: "#a16207",
  },
  editorCard: {
    background: "#fff", borderRadius: 14, padding: 16,
    border: "1px solid #eef1f5", boxShadow: "0 2px 14px rgba(15,23,42,.06)",
  },
  hint: {
    fontSize: 12, color: "#64748b", marginBottom: 10, padding: "8px 12px",
    background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0",
  },
  status: (color) => ({ fontSize: 12, color, fontWeight: 600 }),
};

const LATEX_ONLINE_URL = "https://latexonline.cc/compile";
const OVERLEAF_URL = "https://www.overleaf.com/docs";

function isLatex(doc) {
  return (doc?.format === "latex") ||
         (doc?.markdown || "").trimStart().startsWith("\\documentclass");
}

export default function TailoredResumeEditor() {
  const { resumeId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState("");
  const [compiling, setCompiling] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getTailoredResume(resumeId)
      .then((d) => { setDoc(d); setContent(d.markdown || ""); })
      .catch(() => setError("Could not load this tailored resume."));
  }, [resumeId]);

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await saveTailoredResume(resumeId, content);
      setDoc(updated);
      setSavedAt(new Date());
    } catch {
      setError("Save failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleDownloadMarkdown() {
    window.print();
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Copy failed — select the text manually.");
    }
  }

  function handleOpenInOverleaf() {
    // POST the .tex to Overleaf's snippet importer. We use a hidden form submission
    // because fetch would run into CORS.
    const form = document.createElement("form");
    form.method = "POST";
    form.action = OVERLEAF_URL;
    form.target = "_blank";
    const input = document.createElement("textarea");
    input.name = "snip";
    input.value = content;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  }

  async function handleCompilePdf() {
    setCompiling(true);
    setError("");
    try {
      const resp = await fetch(`${LATEX_ONLINE_URL}?text=${encodeURIComponent(content)}`);
      if (!resp.ok) throw new Error("Compile service returned " + resp.status);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tailored-resume.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError("LaTeX compile failed — try Copy for Overleaf instead.");
    } finally {
      setCompiling(false);
    }
  }

  if (error && !doc) return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate(-1)}>← Back</button>
      <div style={{ background: "#fee2e2", color: "#b91c1c", padding: 16, borderRadius: 10, marginTop: 16 }}>{error}</div>
    </div>
  );
  if (!doc) return <div style={{ textAlign: "center", padding: 80, color: "#64748b" }}>Loading…</div>;

  const latex = isLatex(doc);
  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;
  const targetWords = doc.targetWords || 500;
  const overBudget = wordCount > targetWords * 1.15;

  return (
    <div style={s.page}>
      <div style={s.bar}>
        <button style={s.back} onClick={() => navigate(-1)}>← Back to job</button>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {savedAt && <span style={s.status("#16a34a")}>✓ Saved</span>}
          {latex ? (
            <>
              <button onClick={handleCopy} style={s.btnOutline}>
                {copied ? "✓ Copied" : "Copy .tex"}
              </button>
              <button onClick={handleOpenInOverleaf} style={s.btnOutline}>
                Open in Overleaf ↗
              </button>
              <button onClick={handleCompilePdf} disabled={compiling} style={s.btnOutline}>
                {compiling ? "Compiling…" : "Compile to PDF"}
              </button>
            </>
          ) : (
            <button onClick={handleDownloadMarkdown} style={s.btnOutline}>
              Download PDF
            </button>
          )}
          <button onClick={handleSave} disabled={saving} style={{ ...s.btnPrimary, opacity: saving ? 0.7 : 1 }}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>

      <div style={s.meta}>
        <span style={s.formatPill}>{latex ? "LaTeX" : "Markdown"}</span>
        <div style={s.metaItem}>
          Words: <span style={{ ...s.metaStrong, color: overBudget ? "#dc2626" : "#0f172a" }}>{wordCount}</span>
          <span style={{ color: "#94a3b8", marginLeft: 6 }}>/ {targetWords} target</span>
        </div>
        <div style={{ width: 1, height: 14, background: "#e2e8f0" }} />
        <div style={s.metaItem}>
          {latex
            ? "Copy to Overleaf for a pixel-perfect PDF, or hit Compile to PDF for a one-click download."
            : "Single-page goal · stay close to target for best fit."}
        </div>
        {error && <div style={{ ...s.status("#dc2626"), marginLeft: "auto" }}>{error}</div>}
      </div>

      {latex && (
        <div style={s.hint}>
          💡 Tip: review the .tex for any placeholder bits (e.g. "Company Name", "First Last") and swap in your real details before compiling.
        </div>
      )}

      <div style={s.editorCard} data-color-mode="light">
        {latex ? (
          <CodeMirror
            value={content}
            height="640px"
            theme="light"
            extensions={[StreamLanguage.define(stex)]}
            basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
            onChange={(v) => setContent(v)}
          />
        ) : (
          <MDEditor
            value={content}
            onChange={(v) => setContent(v || "")}
            height={640}
            preview="live"
            textareaProps={{ placeholder: "Your tailored resume in markdown…" }}
          />
        )}
      </div>

      {/* Print-only target for markdown export */}
      {!latex && (
        <>
          <style>{`
            @media print {
              * { visibility: hidden !important; }
              [data-print-only], [data-print-only] * { visibility: visible !important; }
              [data-print-only] {
                position: fixed !important;
                top: 0 !important; left: 0 !important;
                width: 100vw !important;
                overflow: visible !important;
                background: #fff !important;
                z-index: 9999 !important;
                padding: 24px !important;
              }
              @page { margin: 12mm; }
            }
          `}</style>
          <div
            data-print-only
            aria-hidden="true"
            style={{ position: "absolute", left: "-9999px", top: 0, width: 800, padding: 24, background: "#fff", pointerEvents: "none" }}
          >
            <div data-color-mode="light">
              <MDEditor.Markdown source={content} style={{ background: "#fff", color: "#0f172a" }} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
