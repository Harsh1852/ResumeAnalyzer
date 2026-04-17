import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../../services/api";

const s = {
  page: { minHeight: "calc(100vh - 56px)", display: "flex", alignItems: "center", justifyContent: "center" },
  card: { background: "#fff", borderRadius: 12, padding: "40px 36px", width: "100%", maxWidth: 420, boxShadow: "0 4px 24px rgba(0,0,0,.08)" },
  title: { margin: "0 0 24px", fontSize: 24, fontWeight: 700 },
  label: { display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500 },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 15, outline: "none", marginBottom: 16 },
  btn: { width: "100%", padding: "11px 0", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: "pointer", marginTop: 4 },
  err: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  foot: { textAlign: "center", marginTop: 20, fontSize: 14, color: "#6b7280" },
};

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form.email, form.password, form.name);
      navigate("/verify-otp", { state: { email: form.email } });
    } catch (err) {
      setError(err.response?.data?.error || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>Create Account</h1>
        {error && <p style={s.err}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <label style={s.label}>Full Name</label>
          <input style={s.input} type="text" placeholder="Jane Doe" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <label style={s.label}>Email</label>
          <input style={s.input} type="email" placeholder="jane@example.com" required value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <label style={s.label}>Password <span style={{ color: "#9ca3af", fontWeight: 400 }}>(min. 8 chars, upper + lower + digit)</span></label>
          <input style={s.input} type="password" placeholder="••••••••" required minLength={8} value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <button style={s.btn} type="submit" disabled={loading}>
            {loading ? "Creating account…" : "Create Account"}
          </button>
        </form>
        <p style={s.foot}>Already have an account? <Link to="/login">Sign in</Link></p>
      </div>
    </div>
  );
}
