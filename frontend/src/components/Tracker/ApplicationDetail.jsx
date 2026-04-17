import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getApplication, updateApplication, deleteApplication,
  addInterviewRound, updateInterviewRound, deleteInterviewRound,
  APPLICATION_STATUSES, INTERVIEW_OUTCOMES,
} from "../../services/api";

const s = {
  page: { maxWidth: 980, margin: "28px auto", padding: "0 24px 60px" },
  back: {
    background: "none", border: "none", color: "#2563eb", cursor: "pointer",
    fontSize: 14, padding: 0, marginBottom: 16, fontWeight: 500,
  },
  card: {
    background: "#fff", borderRadius: 14, padding: "24px 28px", marginBottom: 18,
    border: "1px solid #eef1f5", boxShadow: "0 2px 14px rgba(15,23,42,.05)",
  },
  headerRow: {
    display: "flex", alignItems: "flex-start", justifyContent: "space-between",
    gap: 16, marginBottom: 18,
  },
  company: { fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, lineHeight: 1.2 },
  role: { fontSize: 15, color: "#475569", marginTop: 6 },
  statusBlock: {
    display: "flex", alignItems: "center", gap: 10,
    background: "#f8fafc", padding: "10px 14px", borderRadius: 10,
    border: "1px solid #e2e8f0",
  },
  select: {
    padding: "7px 10px", borderRadius: 8, border: "1.5px solid #cbd5e1",
    background: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
    color: "#0f172a",
  },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 },
  field: { display: "flex", flexDirection: "column", gap: 6 },
  label: { fontSize: 12, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: ".06em" },
  input: {
    padding: "9px 12px", borderRadius: 8, border: "1.5px solid #e2e8f0",
    fontSize: 14, fontFamily: "inherit", background: "#fff",
  },
  textarea: {
    padding: "10px 12px", borderRadius: 8, border: "1.5px solid #e2e8f0",
    fontSize: 14, fontFamily: "inherit", background: "#fff", resize: "vertical",
    minHeight: 90,
  },
  sectionTitle: {
    fontSize: 15, fontWeight: 700, color: "#0f172a", marginTop: 0, marginBottom: 14,
    display: "flex", alignItems: "center", gap: 8,
  },
  btnPrimary: {
    background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff",
    border: "none", borderRadius: 10, padding: "10px 18px", fontSize: 13,
    fontWeight: 600, cursor: "pointer", boxShadow: "0 2px 10px rgba(99,102,241,.3)",
    letterSpacing: "-0.005em",
  },
  btnGhost: {
    background: "none", border: "1.5px solid #cbd5e1", color: "#475569",
    borderRadius: 10, padding: "9px 16px", fontSize: 13, fontWeight: 600,
    cursor: "pointer",
  },
  btnDanger: {
    background: "none", border: "1.5px solid #fca5a5", color: "#dc2626",
    borderRadius: 10, padding: "9px 16px", fontSize: 13, fontWeight: 600,
    cursor: "pointer",
  },
  toolbar: { display: "flex", gap: 10, marginTop: 14 },
  round: {
    background: "#f8fafc", borderRadius: 10, padding: "14px 16px",
    border: "1px solid #e2e8f0", marginBottom: 10,
  },
  roundHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: 10, gap: 10,
  },
  outcomeBadge: (outcome) => {
    const colors = {
      PENDING: { bg: "#e2e8f0", fg: "#475569" },
      PASSED: { bg: "#dcfce7", fg: "#15803d" },
      FAILED: { bg: "#fee2e2", fg: "#b91c1c" },
      NO_SHOW: { bg: "#fef3c7", fg: "#92400e" },
      RESCHEDULED: { bg: "#fef9c3", fg: "#854d0e" },
    }[outcome] || { bg: "#e2e8f0", fg: "#475569" };
    return {
      fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20,
      background: colors.bg, color: colors.fg, letterSpacing: ".04em",
    };
  },
  timeline: { borderLeft: "2px solid #e2e8f0", paddingLeft: 14, marginLeft: 4 },
  timelineItem: { position: "relative", paddingBottom: 14 },
  timelineDot: {
    position: "absolute", left: -21, top: 4, width: 10, height: 10,
    borderRadius: "50%", background: "#2563eb", border: "2px solid #fff",
    boxShadow: "0 0 0 2px #2563eb",
  },
  timelineStatus: { fontSize: 13, fontWeight: 600, color: "#0f172a" },
  timelineMeta: { fontSize: 11, color: "#64748b", marginTop: 2 },
  loading: { textAlign: "center", padding: 80, color: "#64748b", fontSize: 15 },
  toast: (color) => ({ fontSize: 12, color, fontWeight: 600 }),
};

function formatDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function RoundEditor({ round, applicationId, onSaved, onDeleted }) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({
    roundName: round.roundName || "",
    scheduledAt: round.scheduledAt || "",
    interviewer: round.interviewer || "",
    outcome: round.outcome || "PENDING",
    notes: round.notes || "",
  });
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const updated = await updateInterviewRound(applicationId, round.roundId, form);
      onSaved(updated);
      setEdit(false);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this round?")) return;
    setBusy(true);
    try {
      const updated = await deleteInterviewRound(applicationId, round.roundId);
      onDeleted(updated);
    } finally {
      setBusy(false);
    }
  }

  if (!edit) {
    return (
      <div style={s.round}>
        <div style={s.roundHeader}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a" }}>{round.roundName}</div>
            {round.scheduledAt && <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>📅 {formatDate(round.scheduledAt)}</div>}
          </div>
          <span style={s.outcomeBadge(round.outcome)}>{round.outcome}</span>
        </div>
        {round.interviewer && <div style={{ fontSize: 13, color: "#475569", marginBottom: 6 }}>👤 {round.interviewer}</div>}
        {round.notes && <div style={{ fontSize: 13, color: "#334155", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{round.notes}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button style={s.btnGhost} onClick={() => setEdit(true)}>Edit</button>
          <button style={s.btnDanger} onClick={remove} disabled={busy}>Delete</button>
        </div>
      </div>
    );
  }

  return (
    <div style={s.round}>
      <div style={s.grid}>
        <div style={s.field}>
          <label style={s.label}>Round name</label>
          <input style={s.input} value={form.roundName} onChange={(e) => setForm({ ...form, roundName: e.target.value })} />
        </div>
        <div style={s.field}>
          <label style={s.label}>Outcome</label>
          <select style={s.select} value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })}>
            {INTERVIEW_OUTCOMES.map((o) => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div style={s.field}>
          <label style={s.label}>Scheduled</label>
          <input type="datetime-local" style={s.input} value={form.scheduledAt?.slice(0, 16)} onChange={(e) => setForm({ ...form, scheduledAt: e.target.value })} />
        </div>
        <div style={s.field}>
          <label style={s.label}>Interviewer</label>
          <input style={s.input} value={form.interviewer} onChange={(e) => setForm({ ...form, interviewer: e.target.value })} />
        </div>
      </div>
      <div style={{ ...s.field, marginTop: 10 }}>
        <label style={s.label}>Notes</label>
        <textarea style={s.textarea} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </div>
      <div style={s.toolbar}>
        <button style={s.btnPrimary} onClick={save} disabled={busy}>{busy ? "Saving…" : "Save round"}</button>
        <button style={s.btnGhost} onClick={() => setEdit(false)}>Cancel</button>
      </div>
    </div>
  );
}

function NewRoundForm({ applicationId, onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ roundName: "", scheduledAt: "", interviewer: "", outcome: "PENDING", notes: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!form.roundName.trim()) { setError("Round name is required"); return; }
    setBusy(true);
    setError("");
    try {
      const updated = await addInterviewRound(applicationId, form);
      onCreated(updated);
      setForm({ roundName: "", scheduledAt: "", interviewer: "", outcome: "PENDING", notes: "" });
      setOpen(false);
    } catch {
      setError("Could not add round.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return <button style={s.btnPrimary} onClick={() => setOpen(true)}>+ Add interview round</button>;
  }
  return (
    <div style={s.round}>
      <div style={s.grid}>
        <div style={s.field}>
          <label style={s.label}>Round name *</label>
          <input style={s.input} placeholder="e.g. Phone Screen" value={form.roundName} onChange={(e) => setForm({ ...form, roundName: e.target.value })} />
        </div>
        <div style={s.field}>
          <label style={s.label}>Outcome</label>
          <select style={s.select} value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })}>
            {INTERVIEW_OUTCOMES.map((o) => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div style={s.field}>
          <label style={s.label}>Scheduled</label>
          <input type="datetime-local" style={s.input} value={form.scheduledAt} onChange={(e) => setForm({ ...form, scheduledAt: e.target.value })} />
        </div>
        <div style={s.field}>
          <label style={s.label}>Interviewer</label>
          <input style={s.input} value={form.interviewer} onChange={(e) => setForm({ ...form, interviewer: e.target.value })} />
        </div>
      </div>
      <div style={{ ...s.field, marginTop: 10 }}>
        <label style={s.label}>Notes</label>
        <textarea style={s.textarea} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </div>
      {error && <div style={{ color: "#dc2626", fontSize: 12, marginTop: 8 }}>{error}</div>}
      <div style={s.toolbar}>
        <button style={s.btnPrimary} onClick={submit} disabled={busy}>{busy ? "Adding…" : "Add round"}</button>
        <button style={s.btnGhost} onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}

export default function ApplicationDetail() {
  const { applicationId } = useParams();
  const navigate = useNavigate();
  const [app, setApp] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  // Editable form state (seeded from loaded app)
  const [form, setForm] = useState({
    company: "", jobTitle: "", location: "", jobUrl: "",
    nextAction: "", nextActionDate: "", notes: "",
  });

  useEffect(() => {
    getApplication(applicationId)
      .then((a) => {
        setApp(a);
        setForm({
          company: a.company || "",
          jobTitle: a.jobTitle || "",
          location: a.location || "",
          jobUrl: a.jobUrl || "",
          nextAction: a.nextAction || "",
          nextActionDate: a.nextActionDate || "",
          notes: a.notes || "",
        });
      })
      .catch(() => setError("Could not load this application."));
  }, [applicationId]);

  async function save() {
    setSaving(true);
    setError("");
    try {
      const updated = await updateApplication(applicationId, form);
      setApp(updated);
      setSavedAt(new Date());
    } catch {
      setError("Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(status) {
    setSaving(true);
    try {
      const updated = await updateApplication(applicationId, { status });
      setApp(updated);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this application and all its interview rounds? This cannot be undone.")) return;
    try {
      await deleteApplication(applicationId);
      navigate("/tracker");
    } catch {
      setError("Delete failed.");
    }
  }

  if (error && !app) return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate("/tracker")}>← Back to tracker</button>
      <div style={{ background: "#fee2e2", color: "#b91c1c", padding: 14, borderRadius: 10 }}>{error}</div>
    </div>
  );
  if (!app) return <div style={s.loading}>Loading…</div>;

  return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate("/tracker")}>← Back to tracker</button>

      <div style={s.card}>
        <div style={s.headerRow}>
          <div>
            <h1 style={s.company}>{app.company}</h1>
            <div style={s.role}>{app.jobTitle}</div>
          </div>
          <div style={s.statusBlock}>
            <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>Status</span>
            <select style={s.select} value={app.status} onChange={(e) => changeStatus(e.target.value)} disabled={saving}>
              {APPLICATION_STATUSES.map((st) => <option key={st}>{st}</option>)}
            </select>
          </div>
        </div>

        <div style={s.grid}>
          <div style={s.field}>
            <label style={s.label}>Company</label>
            <input style={s.input} value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Job title</label>
            <input style={s.input} value={form.jobTitle} onChange={(e) => setForm({ ...form, jobTitle: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Location</label>
            <input style={s.input} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Job URL</label>
            <input style={s.input} value={form.jobUrl} onChange={(e) => setForm({ ...form, jobUrl: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Next action</label>
            <input style={s.input} placeholder="e.g. Send follow-up email" value={form.nextAction} onChange={(e) => setForm({ ...form, nextAction: e.target.value })} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Next action date</label>
            <input type="date" style={s.input} value={form.nextActionDate?.slice(0, 10)} onChange={(e) => setForm({ ...form, nextActionDate: e.target.value })} />
          </div>
        </div>

        <div style={{ ...s.field, marginTop: 14 }}>
          <label style={s.label}>Notes</label>
          <textarea style={s.textarea} placeholder="Anything useful — recruiter contact, prep notes, follow-up threads…" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div style={s.toolbar}>
          <button style={s.btnPrimary} onClick={save} disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
          {savedAt && <span style={s.toast("#16a34a")}>✓ Saved</span>}
          {error && <span style={s.toast("#dc2626")}>{error}</span>}
          <div style={{ flex: 1 }} />
          <button style={s.btnDanger} onClick={remove}>Delete application</button>
        </div>
      </div>

      {/* Interview rounds */}
      <div style={s.card}>
        <h2 style={s.sectionTitle}>🎤 Interview Rounds</h2>
        {(app.interviewRounds || []).length === 0 ? (
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 14 }}>No rounds yet. Add one once you've scheduled your first interview.</div>
        ) : (
          (app.interviewRounds || []).map((r) => (
            <RoundEditor
              key={r.roundId}
              round={r}
              applicationId={applicationId}
              onSaved={setApp}
              onDeleted={setApp}
            />
          ))
        )}
        <NewRoundForm applicationId={applicationId} onCreated={setApp} />
      </div>

      {/* Status timeline */}
      <div style={s.card}>
        <h2 style={s.sectionTitle}>🕐 Status Timeline</h2>
        <div style={s.timeline}>
          {(app.statusHistory || []).slice().reverse().map((h, i) => (
            <div key={i} style={s.timelineItem}>
              <div style={s.timelineDot} />
              <div style={s.timelineStatus}>{h.status}</div>
              <div style={s.timelineMeta}>
                {formatDate(h.changedAt)}
                {h.note && ` · ${h.note}`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
