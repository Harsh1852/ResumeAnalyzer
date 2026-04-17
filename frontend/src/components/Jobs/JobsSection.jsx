import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJobs, searchJobs } from "../../services/api";

const s = {
  card: {
    background: "#fff", borderRadius: 14, padding: "26px 30px",
    boxShadow: "0 2px 14px rgba(15,23,42,.06)", marginBottom: 20,
    border: "1px solid #eef1f5",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 18,
  },
  title: { fontSize: 18, fontWeight: 700, margin: 0, color: "#0f172a" },
  subtitle: { fontSize: 13, color: "#64748b", marginTop: 4 },
  btn: (primary) => ({
    background: primary ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "#fff",
    color: primary ? "#fff" : "#6366f1",
    border: primary ? "none" : "1.5px solid #6366f1",
    borderRadius: 10, padding: "9px 18px", fontSize: 13, fontWeight: 600,
    cursor: "pointer", transition: "all .15s", boxShadow: primary ? "0 2px 10px rgba(99,102,241,.3)" : "none",
  }),
  group: { marginBottom: 22 },
  groupTitle: {
    fontSize: 13, fontWeight: 700, color: "#475569", textTransform: "uppercase",
    letterSpacing: ".06em", marginBottom: 10,
  },
  jobGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 },
  jobCard: {
    display: "block", textDecoration: "none", color: "inherit",
    background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
    padding: "16px 18px", transition: "all .18s",
    boxShadow: "0 1px 2px rgba(0,0,0,.03)",
  },
  jobTitle: { fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4, lineHeight: 1.3 },
  company: { fontSize: 13, color: "#475569", fontWeight: 500 },
  meta: { display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, fontSize: 12, color: "#64748b" },
  pill: (bg, fg) => ({
    background: bg, color: fg, padding: "3px 9px", borderRadius: 20,
    fontSize: 11, fontWeight: 600,
  }),
  empty: {
    textAlign: "center", color: "#64748b", padding: "40px 20px", fontSize: 14,
    border: "1.5px dashed #e2e8f0", borderRadius: 12,
  },
  skeleton: {
    height: 110, borderRadius: 12, background: "linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%)",
    backgroundSize: "200% 100%", animation: "shine 1.4s infinite",
  },
};

function formatSalary(min, max) {
  if (!min && !max) return null;
  const fmt = (n) => `$${Math.round(n / 1000)}k`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  return fmt(min || max);
}

function JobCard({ job }) {
  const [hover, setHover] = useState(false);
  const salary = formatSalary(job.salaryMin, job.salaryMax);
  return (
    <Link
      to={`/jobs/${job.jobId}`}
      style={{
        ...s.jobCard,
        ...(hover ? { transform: "translateY(-2px)", boxShadow: "0 8px 24px rgba(37,99,235,.12)", borderColor: "#bfdbfe" } : null),
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={s.jobTitle}>{job.title || "Untitled role"}</div>
      <div style={s.company}>{job.company || "—"}</div>
      <div style={s.meta}>
        {job.location && <span>📍 {job.location}</span>}
        {salary && <span style={s.pill("#dcfce7", "#15803d")}>{salary}</span>}
      </div>
    </Link>
  );
}

export default function JobsSection({ resultId }) {
  const [jobs, setJobs] = useState(null); // null = initial, [] = loaded empty
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!resultId) return;
    listJobs(resultId)
      .then((data) => setJobs(data.jobs || []))
      .catch(() => setError("Could not load jobs."))
      .finally(() => setLoading(false));
  }, [resultId]);

  async function handleSearch() {
    setSearching(true);
    setError("");
    try {
      const data = await searchJobs(resultId);
      setJobs(data.jobs || []);
    } catch (e) {
      setError("Job search failed. Please try again.");
    } finally {
      setSearching(false);
    }
  }

  // Group by role
  const grouped = (jobs || []).reduce((acc, j) => {
    const key = j.roleTitle || "Other";
    (acc[key] = acc[key] || []).push(j);
    return acc;
  }, {});

  return (
    <div style={{ ...s.card, borderLeft: "4px solid #0ea5e9" }}>
      <div style={s.header}>
        <div>
          <h2 style={s.title}>💼 Live Job Openings</h2>
          <div style={s.subtitle}>
            Real postings matched to your top roles. Click a job for tailored resume + course recommendations.
          </div>
        </div>
        <button
          onClick={handleSearch}
          disabled={searching}
          style={{ ...s.btn(true), opacity: searching ? 0.7 : 1 }}
        >
          {searching ? "Searching…" : jobs && jobs.length ? "Refresh" : "Find jobs"}
        </button>
      </div>

      {error && <div style={{ color: "#dc2626", fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {loading && (
        <div style={s.jobGrid}>
          {[0, 1, 2, 3].map((i) => <div key={i} style={s.skeleton} />)}
        </div>
      )}

      {!loading && jobs && jobs.length === 0 && (
        <div style={s.empty}>
          No jobs fetched yet. Click <strong>Find jobs</strong> to pull live openings for your top 5 roles.
        </div>
      )}

      {!loading && jobs && jobs.length > 0 && Object.entries(grouped).map(([role, list]) => (
        <div key={role} style={s.group}>
          <div style={s.groupTitle}>{role} · {list.length}</div>
          <div style={s.jobGrid}>
            {list.map((j) => <JobCard key={j.jobId} job={j} />)}
          </div>
        </div>
      ))}

      <style>{`@keyframes shine { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  );
}
