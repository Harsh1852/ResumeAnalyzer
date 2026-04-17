import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import html2pdf from "html2pdf.js";
import { getResult, getResumeViewUrl, deleteUpload, deleteResult } from "../../services/api";

const s = {
  page: { maxWidth: 820, margin: "40px auto", padding: "0 20px 60px" },
  card: { background: "#fff", borderRadius: 12, padding: "28px 32px", boxShadow: "0 2px 12px rgba(0,0,0,.07)", marginBottom: 20 },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 },
  sectionTitle: { fontSize: 17, fontWeight: 700, margin: "0 0 16px" },
  score: { fontSize: 48, fontWeight: 800, color: "#2563eb", lineHeight: 1 },
  scoreLabel: { color: "#6b7280", fontSize: 14, marginTop: 4 },
  summary: { color: "#374151", lineHeight: 1.6, fontSize: 15 },
  roleCard: { border: "1px solid #e5e7eb", borderRadius: 10, padding: "16px 20px", marginBottom: 12 },
  roleTitle: { fontWeight: 700, fontSize: 16, marginBottom: 4 },
  matchBadge: (pct) => ({
    display: "inline-block", fontSize: 12, fontWeight: 700, padding: "2px 10px",
    borderRadius: 20, background: pct >= 80 ? "#dcfce7" : pct >= 60 ? "#fef9c3" : "#fee2e2",
    color: pct >= 80 ? "#15803d" : pct >= 60 ? "#854d0e" : "#b91c1c",
    marginBottom: 6,
  }),
  companies: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 },
  chip: { fontSize: 12, padding: "3px 10px", background: "#eff6ff", color: "#1d4ed8", borderRadius: 20, fontWeight: 500 },
  list: { paddingLeft: 20, margin: "0", lineHeight: 1.8, color: "#374151", fontSize: 15 },
  tagRow: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 },
  tag: (color) => ({ fontSize: 13, padding: "4px 12px", background: color + "18", color, borderRadius: 20, fontWeight: 500 }),
  backBtn: { background: "none", border: "none", color: "#2563eb", cursor: "pointer", fontSize: 14, padding: 0, marginBottom: 20 },
  loading: { textAlign: "center", padding: "80px 0", color: "#6b7280", fontSize: 16 },
  tabBar: { display: "flex", gap: 4, marginBottom: 20, background: "#f3f4f6", borderRadius: 10, padding: 4 },
  tab: (active) => ({
    flex: 1, padding: "8px 0", border: "none", cursor: "pointer", borderRadius: 8, fontSize: 14, fontWeight: 600,
    background: active ? "#fff" : "transparent",
    color: active ? "#2563eb" : "#6b7280",
    boxShadow: active ? "0 1px 4px rgba(0,0,0,.10)" : "none",
    transition: "all .15s",
  }),
};

function ScoreRing({ score }) {
  const color = score >= 75 ? "#16a34a" : score >= 50 ? "#d97706" : "#dc2626";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ ...s.score, color }}>{score}</div>
      <div style={s.scoreLabel}>Resume Score</div>
      <div style={{ marginTop: 8, height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${score}%`, background: color, borderRadius: 3, transition: "width 1s" }} />
      </div>
    </div>
  );
}

export default function ReportView() {
  const { resultId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("report");
  const [resumeUrl, setResumeUrl] = useState(null);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const reportRef = useRef();

  useEffect(() => {
    getResult(resultId)
      .then(setResult)
      .catch(() => setError("Could not load report. It may still be processing."));
  }, [resultId]);

  function handleDownloadPDF() {
    if (!reportRef.current) return;
    setDownloading(true);
    html2pdf().set({
      margin: 10,
      filename: "resume-analysis-report.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["avoid-all", "css", "legacy"] },
    }).from(reportRef.current).save().finally(() => setDownloading(false));
  }

  async function handleDelete() {
    if (!window.confirm("Delete this resume and its report? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteResult(resultId);
      await deleteUpload(result.uploadId);
      navigate("/dashboard");
    } catch {
      alert("Delete failed. Please try again.");
      setDeleting(false);
    }
  }

  function handleResumeTab() {
    setActiveTab("resume");
    if (!resumeUrl && result?.uploadId) {
      setResumeLoading(true);
      getResumeViewUrl(result.uploadId)
        .then((data) => setResumeUrl(data.viewUrl))
        .catch(() => setResumeUrl("error"))
        .finally(() => setResumeLoading(false));
    }
  }

  if (error) return (
    <div style={s.page}>
      <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>
      <div style={{ ...s.card, color: "#dc2626" }}>{error}</div>
    </div>
  );

  if (!result) return <div style={s.loading}>Loading your report…</div>;

  const { resumeScore, summary, resumeSectionsReview = {}, criticalImprovements = [],
    topRoles = [], jobSearchStrategies = [], skillsToHighlight = [],
    skillsToDevelop = [], keyAchievements = [] } = result;

  return (
    <div style={s.page}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>
        {activeTab === "report" && (
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleDownloadPDF}
              disabled={downloading}
              style={{ background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "8px 18px", fontSize: 14, fontWeight: 600, cursor: downloading ? "default" : "pointer", opacity: downloading ? 0.7 : 1 }}
            >
              {downloading ? "Generating…" : "Download PDF"}
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              style={{ background: "none", border: "1px solid #fca5a5", color: "#dc2626", borderRadius: 8, padding: "8px 18px", fontSize: 14, fontWeight: 600, cursor: deleting ? "default" : "pointer", opacity: deleting ? 0.7 : 1 }}
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        )}
      </div>

      <div style={s.tabBar}>
        <button style={s.tab(activeTab === "report")} onClick={() => setActiveTab("report")}>Analysis Report</button>
        <button style={s.tab(activeTab === "resume")} onClick={handleResumeTab}>View Resume</button>
      </div>

      {activeTab === "resume" && (
        <div style={s.card}>
          {resumeLoading && <div style={{ textAlign: "center", color: "#6b7280", padding: "40px 0" }}>Loading resume...</div>}
          {resumeUrl === "error" && <div style={{ color: "#dc2626" }}>Could not load resume file.</div>}
          {resumeUrl && resumeUrl !== "error" && (
            <iframe
              src={resumeUrl}
              title="Resume"
              style={{ width: "100%", height: "80vh", border: "none", borderRadius: 6 }}
            />
          )}
        </div>
      )}

      {activeTab === "report" && <div ref={reportRef}>
      {/* Score + Summary */}
      <div style={{ ...s.card, display: "grid", gridTemplateColumns: "140px 1fr", gap: 32, alignItems: "start" }}>
        <ScoreRing score={resumeScore || 0} />
        <div>
          <h2 style={{ ...s.sectionTitle, marginBottom: 10 }}>Profile Summary</h2>
          <p style={s.summary}>{summary}</p>
          {keyAchievements.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, color: "#374151" }}>Key Achievements</div>
              <ul style={s.list}>
                {keyAchievements.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Resume Sections Review */}
      {Object.keys(resumeSectionsReview).length > 0 && (
        <div style={{ ...s.card, borderLeft: "4px solid #7c3aed" }}>
          <h2 style={s.sectionTitle}>Resume Section-by-Section Review</h2>
          {[
            ["professional_summary", "Professional Summary"],
            ["work_experience", "Work Experience"],
            ["skills_section", "Skills"],
            ["education", "Education"],
            ["overall_presentation", "Overall Presentation"],
          ].map(([key, label]) => resumeSectionsReview[key] ? (
            <div key={key} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#7c3aed", marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 14, color: "#374151", lineHeight: 1.6 }}>{resumeSectionsReview[key]}</div>
            </div>
          ) : null)}
        </div>
      )}

      {/* Critical Improvements */}
      {criticalImprovements.length > 0 && (
        <div style={{ ...s.card, borderLeft: "4px solid #f59e0b" }}>
          <h2 style={s.sectionTitle}>Critical Improvements</h2>
          <ul style={{ ...s.list, paddingLeft: 18 }}>
            {criticalImprovements.map((item, i) => (
              <li key={i} style={{ marginBottom: 10, color: "#374151" }}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Skills */}
      <div style={s.card}>
        <h2 style={s.sectionTitle}>Skills</h2>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>Highlight These</div>
          <div style={s.tagRow}>{skillsToHighlight.map((sk, i) => <span key={i} style={s.tag("#16a34a")}>{sk}</span>)}</div>
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6 }}>Consider Developing</div>
          <div style={s.tagRow}>{skillsToDevelop.map((sk, i) => <span key={i} style={s.tag("#d97706")}>{sk}</span>)}</div>
        </div>
      </div>

      {/* Top Roles */}
      <div style={s.card}>
        <h2 style={s.sectionTitle}>Top Matching Roles</h2>
        {topRoles.map((role, i) => (
          <div key={i} style={s.roleCard}>
            <div style={s.header}>
              <div style={s.roleTitle}>{role.title}</div>
              <span style={s.matchBadge(role.match_percentage)}>{role.match_percentage}% match</span>
            </div>
            <div style={{ color: "#6b7280", fontSize: 14, marginBottom: 10 }}>{role.reason}</div>
            {(role.resume_gaps || []).length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>Gaps to address</div>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {(role.resume_gaps || []).map((gap, k) => (
                    <li key={k} style={{ fontSize: 13, color: "#7f1d1d", marginBottom: 3 }}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
            {(role.application_tips || []).length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#2563eb", marginBottom: 4 }}>How to apply</div>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {(role.application_tips || []).map((tip, k) => (
                    <li key={k} style={{ fontSize: 13, color: "#1e40af", marginBottom: 4, lineHeight: 1.5 }}>{tip}</li>
                  ))}
                </ul>
              </div>
            )}
            <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>Target Companies</div>
            <div style={s.companies}>
              {(role.target_companies || []).map((c, j) => <span key={j} style={s.chip}>{c}</span>)}
            </div>
          </div>
        ))}
      </div>

      {/* Job Search Strategies */}
      <div style={s.card}>
        <h2 style={s.sectionTitle}>Job Search Strategies</h2>
        <ol style={s.list}>
          {jobSearchStrategies.map((strategy, i) => <li key={i} style={{ marginBottom: 6 }}>{strategy}</li>)}
        </ol>
      </div>
      </div>}
    </div>
  );
}
