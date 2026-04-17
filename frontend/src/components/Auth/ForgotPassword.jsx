import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { forgotPassword } from "../../services/api";

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

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email.trim().toLowerCase());
      navigate("/reset-password", { state: { email: email.trim().toLowerCase() } });
    } catch (err) {
      setError(err.response?.data?.error || "Failed to send reset code. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>Forgot Password</h1>
        <p style={s.sub}>Enter your email and we'll send you a reset code.</p>
        {error && <p style={s.err}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <label style={s.label}>Email</label>
          <input
            style={s.input}
            type="email"
            placeholder="jane@example.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button style={s.btn} type="submit" disabled={loading}>
            {loading ? "Sending…" : "Send Reset Code"}
          </button>
        </form>
        <p style={s.foot}><Link to="/login">← Back to Sign In</Link></p>
      </div>
    </div>
  );
}
