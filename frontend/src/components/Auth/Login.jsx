import React, { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { login } from "../../services/api";

const s = {
  page: { minHeight: "calc(100vh - 56px)", display: "flex", alignItems: "center", justifyContent: "center" },
  card: { background: "#fff", borderRadius: 12, padding: "40px 36px", width: "100%", maxWidth: 420, boxShadow: "0 4px 24px rgba(0,0,0,.08)" },
  title: { margin: "0 0 24px", fontSize: 24, fontWeight: 700 },
  label: { display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500 },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 15, outline: "none", marginBottom: 16 },
  btn: { width: "100%", padding: "11px 0", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: "pointer", marginTop: 4 },
  err: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  ok: { color: "#16a34a", fontSize: 14, marginBottom: 12 },
  foot: { textAlign: "center", marginTop: 20, fontSize: 14, color: "#6b7280" },
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [verified, setVerified] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (location.state?.verified) setVerified(true);
    if (localStorage.getItem("idToken")) navigate("/dashboard", { replace: true });
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(form.email, form.password);
      localStorage.setItem("idToken", data.idToken);
      localStorage.setItem("accessToken", data.accessToken);
      localStorage.setItem("refreshToken", data.refreshToken);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const msg = err.response?.data?.error || "Login failed. Check your credentials.";
      if (msg.includes("verify")) {
        navigate("/verify-otp", { state: { email: form.email } });
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>Sign In</h1>
        {verified && <p style={s.ok}>Email verified! You can now sign in.</p>}
        {error && <p style={s.err}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <label style={s.label}>Email</label>
          <input style={s.input} type="email" placeholder="jane@example.com" required value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <label style={s.label}>Password</label>
          <input style={s.input} type="password" placeholder="••••••••" required value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <button style={s.btn} type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
        <p style={s.foot}>Don't have an account? <Link to="/register">Create one</Link></p>
      </div>
    </div>
  );
}
