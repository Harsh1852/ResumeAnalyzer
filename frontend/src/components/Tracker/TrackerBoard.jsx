import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  listApplications, getApplicationStats, updateApplication,
  APPLICATION_STATUSES,
} from "../../services/api";

const STATUS_COLORS = {
  "Wishlist": { bg: "#f1f5f9", fg: "#475569", accent: "#94a3b8" },
  "Applied": { bg: "#dbeafe", fg: "#1e40af", accent: "#3b82f6" },
  "Phone Screen": { bg: "#ede9fe", fg: "#6d28d9", accent: "#8b5cf6" },
  "Technical Interview": { bg: "#fef3c7", fg: "#92400e", accent: "#f59e0b" },
  "Onsite": { bg: "#fed7aa", fg: "#9a3412", accent: "#f97316" },
  "Offer": { bg: "#dcfce7", fg: "#15803d", accent: "#16a34a" },
  "Rejected": { bg: "#fee2e2", fg: "#b91c1c", accent: "#ef4444" },
  "Ghosted": { bg: "#f3f4f6", fg: "#4b5563", accent: "#9ca3af" },
};

const s = {
  page: { maxWidth: 1400, margin: "28px auto", padding: "0 24px 60px" },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 22,
  },
  title: { fontSize: 28, fontWeight: 800, margin: 0, color: "#09090b", letterSpacing: "-0.02em" },
  subtitle: { fontSize: 14, color: "#64748b", marginTop: 4 },
  primaryBtn: {
    background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff",
    border: "none", borderRadius: 10, padding: "11px 20px", fontSize: 14,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 14px rgba(99,102,241,.35)",
    textDecoration: "none", display: "inline-block", letterSpacing: "-0.005em",
  },
  statsRow: {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 14,
    marginBottom: 26,
  },
  statCard: {
    background: "#fff", borderRadius: 12, padding: "18px 20px",
    boxShadow: "0 1px 6px rgba(15,23,42,.05)", border: "1px solid #eef1f5",
  },
  statLabel: { fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em" },
  statValue: { fontSize: 28, fontWeight: 800, color: "#0f172a", marginTop: 6, lineHeight: 1 },
  statSub: { fontSize: 12, color: "#64748b", marginTop: 4 },
  board: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: 14, alignItems: "start",
  },
  column: {
    background: "#f8fafc", borderRadius: 12, padding: "14px 12px 16px",
    minHeight: 200, border: "1px solid #eef1f5",
  },
  columnHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 12, padding: "0 4px",
  },
  columnTitle: { fontSize: 13, fontWeight: 700, color: "#0f172a" },
  countPill: {
    fontSize: 11, fontWeight: 700, padding: "2px 9px", borderRadius: 20,
  },
  appCard: {
    background: "#fff", borderRadius: 10, padding: "12px 14px", marginBottom: 10,
    boxShadow: "0 1px 4px rgba(15,23,42,.05)", border: "1px solid #e2e8f0",
    cursor: "pointer", transition: "all .15s", textDecoration: "none", color: "inherit",
    display: "block",
  },
  company: { fontSize: 14, fontWeight: 700, color: "#0f172a", marginBottom: 2 },
  role: { fontSize: 13, color: "#475569", marginBottom: 8 },
  cardMeta: { fontSize: 11, color: "#64748b", display: "flex", gap: 10, flexWrap: "wrap" },
  roundsPill: {
    fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
    background: "#e0e7ff", color: "#3730a3",
  },
  nextActionPill: {
    fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
    background: "#fef3c7", color: "#92400e",
  },
  empty: {
    textAlign: "center", color: "#94a3b8", fontSize: 12, padding: "24px 12px",
    border: "1.5px dashed #e2e8f0", borderRadius: 8,
  },
  loading: { textAlign: "center", padding: 80, color: "#64748b", fontSize: 15 },
  error: {
    background: "#fee2e2", color: "#b91c1c", padding: 14, borderRadius: 10,
    marginBottom: 20, fontSize: 14,
  },
};

function ApplicationCard({ app }) {
  const [hover, setHover] = useState(false);
  const rounds = (app.interviewRounds || []).length;
  return (
    <Link
      to={`/tracker/${app.applicationId}`}
      style={{
        ...s.appCard,
        ...(hover ? { transform: "translateY(-2px)", boxShadow: "0 6px 18px rgba(15,23,42,.09)", borderColor: "#bfdbfe" } : null),
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={s.company}>{app.company}</div>
      <div style={s.role}>{app.jobTitle}</div>
      <div style={s.cardMeta}>
        {app.location && <span>📍 {app.location}</span>}
        {rounds > 0 && <span style={s.roundsPill}>{rounds} round{rounds > 1 ? "s" : ""}</span>}
        {app.nextAction && <span style={s.nextActionPill}>⏰ {app.nextAction}</span>}
      </div>
    </Link>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div style={s.statCard}>
      <div style={s.statLabel}>{label}</div>
      <div style={s.statValue}>{value}</div>
      {sub && <div style={s.statSub}>{sub}</div>}
    </div>
  );
}

export default function TrackerBoard() {
  const [apps, setApps] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [a, st] = await Promise.all([listApplications(), getApplicationStats()]);
      setApps(a.applications || []);
      setStats(st);
    } catch {
      setError("Could not load applications.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <div style={s.loading}>Loading your tracker…</div>;

  const grouped = APPLICATION_STATUSES.reduce((acc, st) => { acc[st] = []; return acc; }, {});
  apps.forEach((a) => {
    const bucket = grouped[a.status] || (grouped[a.status] = []);
    bucket.push(a);
  });

  const pct = (n) => `${Math.round((n || 0) * 100)}%`;

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div>
          <h1 style={s.title}>📋 Application Tracker</h1>
          <div style={s.subtitle}>Every role you've wished for, applied to, or interviewed for — in one place.</div>
        </div>
        <Link to="/tracker/new" style={s.primaryBtn}>+ New application</Link>
      </div>

      {error && <div style={s.error}>{error}</div>}

      {stats && (
        <div style={s.statsRow}>
          <StatCard label="Total" value={stats.total} />
          <StatCard label="Active" value={stats.active} sub="In flight now" />
          <StatCard label="Response rate" value={pct(stats.responseRate)} sub="Applied → got a call" />
          <StatCard label="Offer rate" value={pct(stats.offerRate)} sub="Applied → offer" />
        </div>
      )}

      <div style={s.board}>
        {APPLICATION_STATUSES.map((status) => {
          const colors = STATUS_COLORS[status];
          const items = grouped[status];
          return (
            <div key={status} style={{ ...s.column, borderTop: `3px solid ${colors.accent}` }}>
              <div style={s.columnHeader}>
                <div style={s.columnTitle}>{status}</div>
                <div style={{ ...s.countPill, background: colors.bg, color: colors.fg }}>{items.length}</div>
              </div>
              {items.length === 0 ? (
                <div style={s.empty}>No applications</div>
              ) : (
                items.map((a) => <ApplicationCard key={a.applicationId} app={a} />)
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
