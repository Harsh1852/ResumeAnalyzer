import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApplication, APPLICATION_STATUSES } from "../../services/api";

const s = {
  page: { maxWidth: 680, margin: "32px auto", padding: "0 24px 60px" },
  back: {
    background: "none", border: "none", color: "#2563eb", cursor: "pointer",
    fontSize: 14, padding: 0, marginBottom: 18, fontWeight: 500,
  },
  card: {
    background: "#fff", borderRadius: 14, padding: "28px 32px",
    border: "1px solid #eef1f5", boxShadow: "0 2px 14px rgba(15,23,42,.06)",
  },
  title: { fontSize: 22, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" },
  subtitle: { fontSize: 14, color: "#64748b", marginBottom: 22 },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 },
  field: { display: "flex", flexDirection: "column", gap: 6 },
  fieldFull: { display: "flex", flexDirection: "column", gap: 6, gridColumn: "1 / -1" },
  label: { fontSize: 12, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: ".06em" },
  input: {
    padding: "10px 13px", borderRadius: 8, border: "1.5px solid #e2e8f0",
    fontSize: 14, fontFamily: "inherit", background: "#fff",
  },
  select: {
    padding: "10px 13px", borderRadius: 8, border: "1.5px solid #e2e8f0",
    fontSize: 14, background: "#fff", cursor: "pointer",
  },
  textarea: {
    padding: "11px 13px", borderRadius: 8, border: "1.5px solid #e2e8f0",
    fontSize: 14, fontFamily: "inherit", background: "#fff", resize: "vertical",
    minHeight: 100,
  },
  toolbar: { display: "flex", gap: 10, marginTop: 22 },
  btnPrimary: {
    background: "linear-gradient(135deg,#2563eb,#1d4ed8)", color: "#fff",
    border: "none", borderRadius: 10, padding: "11px 22px", fontSize: 14,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 14px rgba(37,99,235,.3)",
  },
  btnGhost: {
    background: "none", border: "1.5px solid #cbd5e1", color: "#475569",
    borderRadius: 10, padding: "10px 20px", fontSize: 14, fontWeight: 600,
    cursor: "pointer",
  },
  error: { color: "#dc2626", fontSize: 13, marginTop: 10 },
};

export default function NewApplication() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    company: "",
    jobTitle: "",
    location: "",
    jobUrl: "",
    status: "Wishlist",
    nextAction: "",
    nextActionDate: "",
    notes: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!form.company.trim() || !form.jobTitle.trim()) {
      setError("Company and job title are required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await createApplication(form);
      navigate(`/tracker/${created.applicationId}`);
    } catch {
      setError("Could not create application.");
      setBusy(false);
    }
  }

  return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate("/tracker")}>← Back to tracker</button>
      <div style={s.card}>
        <h1 style={s.title}>Track a new application</h1>
        <div style={s.subtitle}>Add a job you're applying to (or already wishing for). You can edit everything later.</div>

        <div style={s.grid}>
          <div style={s.field}>
            <label style={s.label}>Company *</label>
            <input style={s.input} value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Job title *</label>
            <input style={s.input} value={form.jobTitle} onChange={(e) => setForm({ ...form, jobTitle: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Location</label>
            <input style={s.input} placeholder="Remote · San Francisco · Hybrid" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Status</label>
            <select style={s.select} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {APPLICATION_STATUSES.map((st) => <option key={st}>{st}</option>)}
            </select>
          </div>
          <div style={s.fieldFull}>
            <label style={s.label}>Job URL</label>
            <input style={s.input} placeholder="https://…" value={form.jobUrl} onChange={(e) => setForm({ ...form, jobUrl: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Next action</label>
            <input style={s.input} placeholder="e.g. Submit resume" value={form.nextAction} onChange={(e) => setForm({ ...form, nextAction: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Next action date</label>
            <input type="date" style={s.input} value={form.nextActionDate} onChange={(e) => setForm({ ...form, nextActionDate: e.target.value })} />
          </div>
          <div style={s.fieldFull}>
            <label style={s.label}>Notes</label>
            <textarea style={s.textarea} placeholder="Recruiter contact, referral, prep notes…" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>

        {error && <div style={s.error}>{error}</div>}

        <div style={s.toolbar}>
          <button style={s.btnPrimary} onClick={submit} disabled={busy}>{busy ? "Creating…" : "Create application"}</button>
          <button style={s.btnGhost} onClick={() => navigate("/tracker")}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
