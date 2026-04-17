import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getJob, fetchCoursesForJob, createTailoredResume, getResult,
} from "../../services/api";

const s = {
  page: { maxWidth: 980, margin: "32px auto", padding: "0 20px 60px" },
  back: {
    background: "none", border: "none", color: "#2563eb", cursor: "pointer",
    fontSize: 14, padding: 0, marginBottom: 18, fontWeight: 500,
  },
  grid: { display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 20 },
  card: {
    background: "#fff", borderRadius: 14, padding: "26px 30px",
    boxShadow: "0 2px 14px rgba(15,23,42,.06)", marginBottom: 20,
    border: "1px solid #eef1f5",
  },
  hero: {
    background: "linear-gradient(135deg,#0f172a,#1e3a8a)",
    color: "#fff", borderRadius: 14, padding: "28px 32px", marginBottom: 20,
    boxShadow: "0 4px 20px rgba(30,58,138,.25)",
  },
  heroTitle: { fontSize: 26, fontWeight: 800, margin: 0, lineHeight: 1.25 },
  heroCompany: { fontSize: 15, opacity: 0.85, marginTop: 6, fontWeight: 500 },
  heroMeta: { display: "flex", flexWrap: "wrap", gap: 10, marginTop: 14 },
  heroPill: {
    background: "rgba(255,255,255,.15)", padding: "5px 12px", borderRadius: 20,
    fontSize: 12, fontWeight: 600, backdropFilter: "blur(4px)",
  },
  sectionTitle: {
    fontSize: 15, fontWeight: 700, color: "#0f172a", margin: "0 0 14px",
    display: "flex", alignItems: "center", gap: 8,
  },
  jd: { fontSize: 14, color: "#334155", lineHeight: 1.7, whiteSpace: "pre-wrap" },
  primaryBtn: {
    background: "linear-gradient(135deg,#2563eb,#1d4ed8)", color: "#fff",
    border: "none", borderRadius: 10, padding: "12px 20px", fontSize: 14,
    fontWeight: 600, cursor: "pointer", width: "100%",
    boxShadow: "0 4px 14px rgba(37,99,235,.3)",
  },
  outlineBtn: {
    background: "#fff", color: "#2563eb", border: "1.5px solid #2563eb",
    borderRadius: 10, padding: "10px 16px", fontSize: 13, fontWeight: 600,
    cursor: "pointer", textDecoration: "none", display: "inline-block",
  },
  courseSkill: {
    fontSize: 13, fontWeight: 700, color: "#0ea5e9", marginBottom: 8,
    textTransform: "uppercase", letterSpacing: ".05em",
  },
  courseLink: {
    display: "block", padding: "10px 12px", borderRadius: 8,
    background: "#f8fafc", border: "1px solid #e2e8f0",
    textDecoration: "none", color: "#0f172a", marginBottom: 8,
    fontSize: 13, transition: "all .15s",
  },
  tag: {
    display: "inline-block", fontSize: 11, fontWeight: 600,
    padding: "3px 10px", borderRadius: 20, background: "#fee2e2",
    color: "#b91c1c", marginRight: 6, marginBottom: 6,
  },
  loadingRow: { color: "#64748b", fontSize: 13, padding: "12px 0" },
};

function pickResumeText(resultLike, fallback) {
  // Reconstruct approximate resume text from stored report fields.
  // The full parsed text isn't carried in results; we approximate from the report summary + achievements + resumeSectionsReview bullets.
  if (!resultLike) return fallback || "";
  const parts = [];
  if (resultLike.summary) parts.push(resultLike.summary);
  if (Array.isArray(resultLike.keyAchievements)) parts.push(...resultLike.keyAchievements);
  if (Array.isArray(resultLike.skillsToHighlight)) parts.push("Skills: " + resultLike.skillsToHighlight.join(", "));
  if (resultLike.resumeSectionsReview) {
    Object.values(resultLike.resumeSectionsReview).forEach((v) => { if (v) parts.push(v); });
  }
  return parts.join("\n\n") || fallback || "";
}

export default function JobDetail() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [courses, setCourses] = useState(null);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getJob(jobId)
      .then(async (j) => {
        setJob(j);
        if (j.resultId) {
          try {
            const r = await getResult(j.resultId);
            setResult(r);
          } catch { /* soft fail */ }
        }
      })
      .catch(() => setError("Could not load this job."));
  }, [jobId]);

  function handleCourses() {
    setCoursesLoading(true);
    fetchCoursesForJob(jobId)
      .then((d) => setCourses(d.courses || []))
      .catch(() => setError("Could not load course recommendations."))
      .finally(() => setCoursesLoading(false));
  }

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const resumeText = pickResumeText(result);
      if (!resumeText || resumeText.length < 50) {
        setError("Unable to build a tailored resume — no original resume text available.");
        setGenerating(false);
        return;
      }
      const tailored = await createTailoredResume(jobId, resumeText);
      navigate(`/tailored-resumes/${tailored.resumeId}`);
    } catch (e) {
      setError("Tailored resume generation failed. Please try again.");
      setGenerating(false);
    }
  }

  if (error && !job) return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate(-1)}>← Back</button>
      <div style={{ ...s.card, color: "#dc2626" }}>{error}</div>
    </div>
  );
  if (!job) return <div style={{ textAlign: "center", padding: 80, color: "#64748b" }}>Loading…</div>;

  const salary = (job.salaryMin || job.salaryMax)
    ? `$${Math.round((job.salaryMin || job.salaryMax) / 1000)}k${job.salaryMax && job.salaryMin ? ` – $${Math.round(job.salaryMax / 1000)}k` : ""}`
    : null;

  return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate(-1)}>← Back to report</button>

      <div style={s.hero}>
        <h1 style={s.heroTitle}>{job.title}</h1>
        <div style={s.heroCompany}>{job.company || "—"}</div>
        <div style={s.heroMeta}>
          {job.location && <span style={s.heroPill}>📍 {job.location}</span>}
          {salary && <span style={s.heroPill}>💰 {salary}</span>}
          {job.matchPercentage != null && (
            <span style={s.heroPill}>🎯 {job.matchPercentage}% match to your resume</span>
          )}
        </div>
        {job.redirectUrl && (
          <div style={{ marginTop: 18 }}>
            <a href={job.redirectUrl} target="_blank" rel="noopener noreferrer"
               style={{ ...s.outlineBtn, background: "#fff", color: "#1e3a8a" }}>
              View original posting ↗
            </a>
          </div>
        )}
      </div>

      <div style={s.grid}>
        {/* Left column: JD */}
        <div>
          <div style={s.card}>
            <h3 style={s.sectionTitle}>📄 Job Description</h3>
            <div style={s.jd}>{job.description || "No description provided."}</div>
          </div>

          {(job.resumeGaps || []).length > 0 && (
            <div style={{ ...s.card, borderLeft: "4px solid #ef4444" }}>
              <h3 style={s.sectionTitle}>⚠️ Gaps the hiring manager will notice</h3>
              <div>
                {job.resumeGaps.map((g, i) => <span key={i} style={s.tag}>{g}</span>)}
              </div>
            </div>
          )}
        </div>

        {/* Right column: actions + courses */}
        <div>
          <div style={s.card}>
            <h3 style={s.sectionTitle}>✨ Tailor your resume</h3>
            <div style={{ fontSize: 13, color: "#475569", marginBottom: 14, lineHeight: 1.5 }}>
              Generate a one-page resume rewritten to match this specific job description. You can edit the result.
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              style={{ ...s.primaryBtn, opacity: generating ? 0.7 : 1 }}
            >
              {generating ? "Generating…" : "Generate tailored resume"}
            </button>
            {error && <div style={{ color: "#dc2626", fontSize: 12, marginTop: 10 }}>{error}</div>}
          </div>

          <div style={s.card}>
            <h3 style={s.sectionTitle}>🎓 Courses for missing skills</h3>
            {!courses && !coursesLoading && (
              <button onClick={handleCourses} style={{ ...s.outlineBtn, width: "100%", textAlign: "center" }}>
                Find courses
              </button>
            )}
            {coursesLoading && <div style={s.loadingRow}>Fetching recommendations…</div>}
            {courses && courses.length === 0 && (
              <div style={{ fontSize: 13, color: "#64748b" }}>No skill gaps detected — you're in great shape for this role.</div>
            )}
            {courses && courses.map((c, i) => (
              <div key={i} style={{ marginBottom: 14 }}>
                <div style={s.courseSkill}>{c.skill}</div>
                {(c.recommendations || []).map((r, j) => (
                  <a key={j} href={r.url} target="_blank" rel="noopener noreferrer"
                     style={s.courseLink}
                     onMouseEnter={(e) => e.currentTarget.style.background = "#eff6ff"}
                     onMouseLeave={(e) => e.currentTarget.style.background = "#f8fafc"}>
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>{r.title}</div>
                    <div style={{ fontSize: 11, color: "#64748b" }}>{r.snippet || r.url}</div>
                  </a>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
