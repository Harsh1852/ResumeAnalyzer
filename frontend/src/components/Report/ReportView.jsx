import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getResult } from "../../services/api";

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

  useEffect(() => {
    getResult(resultId)
      .then(setResult)
      .catch(() => setError("Could not load report. It may still be processing."));
  }, [resultId]);

  if (error) return (
    <div style={s.page}>
      <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>
      <div style={{ ...s.card, color: "#dc2626" }}>{error}</div>
    </div>
  );

  if (!result) return <div style={s.loading}>Loading your report…</div>;

  const { resumeScore, summary, topRoles = [], jobSearchStrategies = [],
    skillsToHighlight = [], skillsToDevelop = [], keyAchievements = [] } = result;

  return (
    <div style={s.page}>
      <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>

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
            <div style={{ color: "#6b7280", fontSize: 14, marginBottom: 8 }}>{role.reason}</div>
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
    </div>
  );
}
