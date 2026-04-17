import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { confirmForgotPassword } from "../../services/api";

const s = {
  page: { minHeight: "calc(100vh - 62px)", display: "flex", alignItems: "center", justifyContent: "center" },
  card: { background: "#fff", borderRadius: 12, padding: "40px 36px", width: "100%", maxWidth: 420, boxShadow: "0 4px 24px rgba(0,0,0,.08)" },
  title: { margin: "0 0 8px", fontSize: 24, fontWeight: 700 },
  sub: { margin: "0 0 24px", fontSize: 14, color: "#6b7280" },
  label: { display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500 },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 15, outline: "none", marginBottom: 16, boxSizing: "border-box" },
  btn: { width: "100%", padding: "11px 0", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: "pointer", marginTop: 4 },
  err: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  foot: { textAlign: "center", marginTop: 20, fontSize: 14, color: "#6b7280" },
};

export default function ResetPassword() {
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email || "";
  const [form, setForm] = useState({ code: "", newPassword: "", confirm: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (form.newPassword !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    if (form.newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await confirmForgotPassword(email, form.code, form.newPassword);
      navigate("/login", { state: { verified: true } });
    } catch (err) {
      setError(err.response?.data?.error || "Reset failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>Reset Password</h1>
        <p style={s.sub}>Enter the code sent to <strong>{email}</strong> and your new password.</p>
        {error && <p style={s.err}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <label style={s.label}>Reset Code</label>
          <input
            style={s.input}
            type="text"
            placeholder="6-digit code"
            required
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
          <label style={s.label}>New Password <span style={{ color: "#9ca3af", fontWeight: 400 }}>(min. 8 chars, upper + lower + digit)</span></label>
          <input
            style={s.input}
            type="password"
            placeholder="••••••••"
            required
            value={form.newPassword}
            onChange={(e) => setForm({ ...form, newPassword: e.target.value })}
          />
          <label style={s.label}>Confirm New Password</label>
          <input
            style={s.input}
            type="password"
            placeholder="••••••••"
            required
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          />
          <button style={s.btn} type="submit" disabled={loading}>
            {loading ? "Resetting…" : "Reset Password"}
          </button>
        </form>
        <p style={s.foot}><Link to="/forgot-password">Resend code</Link> · <Link to="/login">Back to Sign In</Link></p>
      </div>
    </div>
  );
}
