import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { pdf } from "@react-pdf/renderer";
import { ReportPDF } from "./ReportPDF";
import { getResult, getResumeViewUrl, deleteUpload, deleteResult } from "../../services/api";
import JobsSection from "../Jobs/JobsSection";

/* ────────────────────────────────────────────────────────────────────────────
 * Full-screen report layout. Top roles are compact cards with "View details →"
 * buttons that route to /results/:id/roles/:idx. The old narrow report format
 * is still rendered — off-screen — so the Download PDF button produces the
 * detailed document the user expects.
 * ──────────────────────────────────────────────────────────────────────────── */

const GOLD_START = "#b8860b";
const GOLD_END = "#d4af37";

const s = {
  shell: { maxWidth: 1280, margin: "32px auto", padding: "0 28px 80px" },
  topBar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    gap: 12, flexWrap: "wrap", marginBottom: 24,
  },
  backBtn: {
    background: "none", border: "none", color: GOLD_START, cursor: "pointer",
    fontSize: 14, padding: 0, fontWeight: 500,
  },
  rightBtns: { display: "flex", gap: 10, flexWrap: "wrap" },
  btnPrimary: {
    background: `linear-gradient(135deg,${GOLD_START},${GOLD_END})`, color: "#fff",
    border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 14px rgba(184,134,11,.3)",
    letterSpacing: "-0.005em",
  },
  btnGhost: {
    background: "#fff", color: "#1c1917",
    border: "1px solid rgba(28,25,23,0.14)", borderRadius: 10,
    padding: "10px 18px", fontSize: 13, fontWeight: 500, cursor: "pointer",
  },
  btnDanger: {
    background: "#fff", color: "#b91c1c",
    border: "1px solid #fca5a5", borderRadius: 10,
    padding: "10px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer",
  },
  tabBar: {
    display: "flex", gap: 4, marginBottom: 24,
    background: "rgba(28,25,23,0.04)", borderRadius: 10, padding: 4,
    border: "1px solid rgba(28,25,23,0.06)", width: "fit-content",
  },
  tab: (active) => ({
    padding: "8px 18px", border: "none", cursor: "pointer", borderRadius: 8,
    fontSize: 14, fontWeight: 600,
    background: active ? "#fff" : "transparent",
    color: active ? GOLD_START : "#78716c",
    boxShadow: active ? "0 1px 3px rgba(0,0,0,.08)" : "none",
    transition: "all .15s",
  }),
  hero: {
    background: "#fff", borderRadius: 18, padding: "32px 36px", marginBottom: 22,
    border: "1px solid rgba(28,25,23,0.06)",
    boxShadow: "0 1px 3px rgba(9,9,11,0.04), 0 6px 24px rgba(184,134,11,0.06)",
    display: "grid", gridTemplateColumns: "180px 1fr", gap: 34, alignItems: "center",
  },
  scoreBlock: { textAlign: "center" },
  scoreNumber: {
    fontSize: 64, fontWeight: 800, lineHeight: 1,
    background: `linear-gradient(135deg,${GOLD_START},${GOLD_END})`,
    WebkitBackgroundClip: "text", backgroundClip: "text",
    color: "transparent", WebkitTextFillColor: "transparent",
    fontFamily: '"Playfair Display", Georgia, serif',
  },
  scoreLabel: { color: "#78716c", fontSize: 13, marginTop: 6, fontWeight: 500, letterSpacing: ".04em", textTransform: "uppercase" },
  scoreBar: { marginTop: 14, height: 5, background: "rgba(28,25,23,0.08)", borderRadius: 3, overflow: "hidden" },
  scoreBarFill: (pct) => ({
    height: "100%", width: `${pct}%`,
    background: `linear-gradient(90deg,${GOLD_START},${GOLD_END})`, borderRadius: 3,
    transition: "width 1s",
  }),
  summary: { color: "#3f3f46", lineHeight: 1.65, fontSize: 15.5 },
  grid2: { display: "grid", gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)", gap: 22, marginBottom: 22 },
  card: {
    background: "#fff", borderRadius: 16, padding: "26px 30px",
    border: "1px solid rgba(28,25,23,0.06)",
    boxShadow: "0 1px 3px rgba(9,9,11,0.04), 0 4px 16px rgba(9,9,11,0.03)",
    marginBottom: 22,
  },
  cardTitle: { fontSize: 17, fontWeight: 700, color: "#1c1917", margin: "0 0 18px", letterSpacing: "-0.01em" },
  roleList: { display: "grid", gap: 12 },
  roleCard: {
    display: "flex", alignItems: "center", gap: 16,
    padding: "16px 20px", borderRadius: 12,
    border: "1px solid rgba(28,25,23,0.08)",
    background: "#fff",
    textDecoration: "none", color: "inherit",
    cursor: "pointer", transition: "all .18s ease",
  },
  roleCardHover: {
    transform: "translateY(-1px)",
    borderColor: GOLD_END,
    boxShadow: "0 8px 24px rgba(184,134,11,.12)",
  },
  roleMatchRing: (pct) => ({
    width: 52, height: 52, borderRadius: "50%",
    display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
    background: pct >= 80
      ? `conic-gradient(${GOLD_END} ${pct * 3.6}deg, rgba(28,25,23,0.06) 0deg)`
      : pct >= 60
      ? `conic-gradient(${GOLD_START} ${pct * 3.6}deg, rgba(28,25,23,0.06) 0deg)`
      : `conic-gradient(#78716c ${pct * 3.6}deg, rgba(28,25,23,0.06) 0deg)`,
  }),
  roleMatchInner: {
    width: 42, height: 42, borderRadius: "50%", background: "#fff",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 13, fontWeight: 800, color: "#1c1917",
  },
  roleMid: { flex: 1, minWidth: 0 },
  roleTitle: { fontSize: 15, fontWeight: 700, color: "#1c1917", marginBottom: 3, letterSpacing: "-0.01em" },
  roleReason: {
    fontSize: 13, color: "#57534e", lineHeight: 1.45,
    display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  roleArrow: {
    color: GOLD_START, fontSize: 20, fontWeight: 400,
    flexShrink: 0, opacity: 0.7, transition: "transform .2s, opacity .2s",
  },
  skillsSection: { marginBottom: 16 },
  skillsSubTitle: {
    fontSize: 11, fontWeight: 700, color: "#78716c",
    textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 8,
  },
  skillsLine: {
    color: "#1c1917", fontSize: 14, lineHeight: 1.65, fontWeight: 500,
  },
  skillInline: {
    display: "inline-block", padding: "2px 9px", borderRadius: 20,
    fontSize: 13, fontWeight: 500, marginRight: 6, marginBottom: 6,
    background: "rgba(184,134,11,0.08)", color: "#78350f",
    border: "1px solid rgba(184,134,11,0.18)",
  },
  skillInlineDev: {
    display: "inline-block", padding: "2px 9px", borderRadius: 20,
    fontSize: 13, fontWeight: 500, marginRight: 6, marginBottom: 6,
    background: "rgba(120,113,108,0.08)", color: "#57534e",
    border: "1px solid rgba(120,113,108,0.2)",
  },
  list: { paddingLeft: 18, margin: 0, lineHeight: 1.75, color: "#3f3f46", fontSize: 14 },
  improvementsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
    gap: 14,
  },
  improvementItem: {
    display: "flex", gap: 14, alignItems: "flex-start",
    padding: "14px 16px", background: "rgba(184,134,11,0.04)",
    border: "1px solid rgba(184,134,11,0.12)", borderRadius: 12,
  },
  improvementNum: {
    width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
    background: `linear-gradient(135deg,${GOLD_START},${GOLD_END})`,
    color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 13, fontWeight: 700,
    boxShadow: "0 2px 6px rgba(184,134,11,0.25)",
  },
  improvementText: {
    flex: 1, fontSize: 14, color: "#3f3f46", lineHeight: 1.55,
  },
  sectionReviewItem: { marginBottom: 14 },
  sectionReviewLabel: { fontSize: 12, fontWeight: 700, color: GOLD_START, marginBottom: 4, letterSpacing: ".03em" },
  sectionReviewText: { fontSize: 14, color: "#3f3f46", lineHeight: 1.6 },
  loading: { textAlign: "center", padding: "80px 0", color: "#78716c", fontSize: 16 },
};

function ScoreRing({ score }) {
  return (
    <div style={s.scoreBlock}>
      <div style={s.scoreNumber}>{score}</div>
      <div style={s.scoreLabel}>Resume Score</div>
      <div style={s.scoreBar}>
        <div style={s.scoreBarFill(score)} />
      </div>
    </div>
  );
}

function RoleCard({ role, index, resultId }) {
  const [hover, setHover] = useState(false);
  const style = hover ? { ...s.roleCard, ...s.roleCardHover } : s.roleCard;
  const arrowStyle = hover
    ? { ...s.roleArrow, transform: "translateX(4px)", opacity: 1 }
    : s.roleArrow;
  return (
    <Link
      to={`/results/${resultId}/roles/${index}`}
      style={style}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={s.roleMatchRing(role.match_percentage || 0)}>
        <div style={s.roleMatchInner}>{role.match_percentage || 0}</div>
      </div>
      <div style={s.roleMid}>
        <div style={s.roleTitle}>{role.title}</div>
        <div style={s.roleReason}>{role.reason}</div>
      </div>
      <div style={arrowStyle}>→</div>
    </Link>
  );
}

function SkillsCard({ highlight, develop }) {
  if (!highlight?.length && !develop?.length) return null;
  return (
    <div style={s.card}>
      <h2 style={s.cardTitle}>Skills</h2>
      {highlight?.length > 0 && (
        <div style={s.skillsSection}>
          <div style={s.skillsSubTitle}>You excel at</div>
          <div>
            {highlight.map((skill, i) => (
              <span key={i} style={s.skillInline}>{skill}</span>
            ))}
          </div>
        </div>
      )}
      {develop?.length > 0 && (
        <div style={s.skillsSection}>
          <div style={s.skillsSubTitle}>Consider developing</div>
          <div>
            {develop.map((skill, i) => (
              <span key={i} style={s.skillInlineDev}>{skill}</span>
            ))}
          </div>
        </div>
      )}
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

  useEffect(() => {
    getResult(resultId)
      .then(setResult)
      .catch(() => setError("Could not load report. It may still be processing."));
  }, [resultId]);

  async function handleDownloadPDF() {
    setDownloading(true);
    try {
      const blob = await pdf(<ReportPDF result={result} />).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "resume-analysis-report.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF generation failed", err);
      alert("Could not generate PDF. Please try again.");
    } finally {
      setDownloading(false);
    }
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
    <div style={s.shell}>
      <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>
      <div style={{ ...s.card, color: "#b91c1c" }}>{error}</div>
    </div>
  );

  if (!result) return <div style={s.loading}>Loading your report…</div>;

  const {
    resumeScore = 0, summary, resumeSectionsReview = {}, criticalImprovements = [],
    topRoles = [], jobSearchStrategies = [], skillsToHighlight = [],
    skillsToDevelop = [], keyAchievements = [],
  } = result;

  return (
    <div style={s.shell}>
      {/* Top bar */}
      <div style={s.topBar}>
        <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>
        {activeTab === "report" && (
          <div style={s.rightBtns}>
            <button onClick={handleDownloadPDF} disabled={downloading} style={{ ...s.btnPrimary, opacity: downloading ? 0.7 : 1 }}>
              {downloading ? "Generating…" : "Download PDF"}
            </button>
            <button onClick={handleDelete} disabled={deleting} style={s.btnDanger}>
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={s.tabBar}>
        <button style={s.tab(activeTab === "report")} onClick={() => setActiveTab("report")}>Analysis Report</button>
        <button style={s.tab(activeTab === "resume")} onClick={handleResumeTab}>View Resume</button>
      </div>

      {activeTab === "resume" && (
        <div style={s.card}>
          {resumeLoading && <div style={{ textAlign: "center", color: "#78716c", padding: "40px 0" }}>Loading resume…</div>}
          {resumeUrl === "error" && <div style={{ color: "#b91c1c" }}>Could not load resume file.</div>}
          {resumeUrl && resumeUrl !== "error" && (
            <iframe
              src={resumeUrl}
              title="Resume"
              style={{ width: "100%", height: "80vh", border: "none", borderRadius: 6 }}
            />
          )}
        </div>
      )}

      {activeTab === "report" && (
        <>
          {/* Hero: score + summary */}
          <div style={s.hero}>
            <ScoreRing score={resumeScore} />
            <div>
              <h1 className="display-serif" style={{ fontSize: 26, fontWeight: 700, margin: "0 0 10px", color: "#1c1917", letterSpacing: "-0.015em" }}>
                Profile Summary
              </h1>
              <p style={s.summary}>{summary}</p>
            </div>
          </div>

          {/* Critical improvements — full width for readability */}
          {criticalImprovements.length > 0 && (
            <div style={{
              ...s.card,
              borderLeft: `4px solid ${GOLD_END}`,
              background: "linear-gradient(180deg, #fff, rgba(212,175,55,0.03))",
            }}>
              <h2 style={s.cardTitle}>
                <span style={{ color: GOLD_START }}>✦</span> Critical Improvements
              </h2>
              <div style={s.improvementsGrid}>
                {criticalImprovements.map((item, i) => (
                  <div key={i} style={s.improvementItem}>
                    <div style={s.improvementNum}>{i + 1}</div>
                    <div style={s.improvementText}>{item}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Two-column grid: roles left (wider), skills+review right */}
          <div style={s.grid2}>
            {/* Left column */}
            <div>
              <div style={s.card}>
                <h2 style={s.cardTitle}>Top Matching Roles</h2>
                <div style={s.roleList}>
                  {topRoles.map((role, i) => (
                    <RoleCard key={i} role={role} index={i} resultId={resultId} />
                  ))}
                </div>
              </div>

              {keyAchievements.length > 0 && (
                <div style={s.card}>
                  <h2 style={s.cardTitle}>Key Achievements</h2>
                  <ul style={s.list}>
                    {keyAchievements.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>
              )}
            </div>

            {/* Right column */}
            <div>
              <SkillsCard highlight={skillsToHighlight} develop={skillsToDevelop} />

              {Object.keys(resumeSectionsReview).length > 0 && (
                <div style={s.card}>
                  <h2 style={s.cardTitle}>Section Review</h2>
                  {[
                    ["professional_summary", "Professional Summary"],
                    ["work_experience", "Work Experience"],
                    ["skills_section", "Skills"],
                    ["education", "Education"],
                    ["overall_presentation", "Overall Presentation"],
                  ].map(([key, label]) => resumeSectionsReview[key] ? (
                    <div key={key} style={s.sectionReviewItem}>
                      <div style={s.sectionReviewLabel}>{label}</div>
                      <div style={s.sectionReviewText}>{resumeSectionsReview[key]}</div>
                    </div>
                  ) : null)}
                </div>
              )}
            </div>
          </div>

          {/* Live jobs — full width */}
          <JobsSection resultId={result.resultId} />

          {/* Strategies — full width */}
          {jobSearchStrategies.length > 0 && (
            <div style={s.card}>
              <h2 style={s.cardTitle}>Job Search Strategies</h2>
              <ol style={s.list}>
                {jobSearchStrategies.map((strategy, i) => <li key={i} style={{ marginBottom: 6 }}>{strategy}</li>)}
              </ol>
            </div>
          )}

        </>
      )}
    </div>
  );
}
