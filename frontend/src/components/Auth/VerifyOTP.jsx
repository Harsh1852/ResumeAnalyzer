import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { verifyOTP, resendOTP } from "../../services/api";

const s = {
  page: { minHeight: "calc(100vh - 56px)", display: "flex", alignItems: "center", justifyContent: "center" },
  card: { background: "#fff", borderRadius: 12, padding: "40px 36px", width: "100%", maxWidth: 420, boxShadow: "0 4px 24px rgba(0,0,0,.08)" },
  title: { margin: "0 0 8px", fontSize: 24, fontWeight: 700 },
  sub: { color: "#6b7280", marginBottom: 24, fontSize: 14 },
  label: { display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500 },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 15, outline: "none", marginBottom: 16, letterSpacing: 6, textAlign: "center" },
  btn: { width: "100%", padding: "11px 0", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: "pointer", marginTop: 4 },
  link: { background: "none", border: "none", color: "#2563eb", cursor: "pointer", fontSize: 14, padding: 0, textDecoration: "underline" },
  err: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  ok: { color: "#16a34a", fontSize: 14, marginBottom: 12 },
  foot: { textAlign: "center", marginTop: 20, fontSize: 14, color: "#6b7280" },
};

export default function VerifyOTP() {
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email || "";
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleVerify(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await verifyOTP(email, code.trim());
      navigate("/login", { state: { verified: true } });
    } catch (err) {
      setError(err.response?.data?.error || "Verification failed. Check the code and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError("");
    setSuccess("");
    try {
      await resendOTP(email);
      setSuccess("A new verification code has been sent to your email.");
    } catch (err) {
      setError(err.response?.data?.error || "Could not resend code.");
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>Verify Your Email</h1>
        <p style={s.sub}>We sent a 6-digit code to <strong>{email || "your email"}</strong>. Enter it below.</p>
        {error && <p style={s.err}>{error}</p>}
        {success && <p style={s.ok}>{success}</p>}
        <form onSubmit={handleVerify}>
          <label style={s.label}>Verification Code</label>
          <input style={s.input} type="text" inputMode="numeric" maxLength={6} placeholder="000000"
            value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required />
          <button style={s.btn} type="submit" disabled={loading || code.length < 6}>
            {loading ? "Verifying…" : "Verify Email"}
          </button>
        </form>
        <p style={s.foot}>
          Didn't get the code?{" "}
          <button style={s.link} type="button" onClick={handleResend}>Resend</button>
        </p>
        <p style={s.foot}><Link to="/register">← Back to registration</Link></p>
      </div>
    </div>
  );
}
