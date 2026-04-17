import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Link, useNavigate } from "react-router-dom";
import Register from "./components/Auth/Register";
import VerifyOTP from "./components/Auth/VerifyOTP";
import Login from "./components/Auth/Login";
import ResumeUpload from "./components/Resume/ResumeUpload";
import ReportView from "./components/Report/ReportView";

const s = {
  nav: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "0 24px", height: 56, background: "#2563eb", color: "#fff",
  },
  navTitle: { fontWeight: 700, fontSize: 18, color: "#fff" },
  navBtn: {
    background: "rgba(255,255,255,.15)", border: "none", color: "#fff",
    padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 14,
  },
};

function Nav() {
  const navigate = useNavigate();
  const token = localStorage.getItem("idToken");

  function logout() {
    localStorage.clear();
    navigate("/login");
  }

  return (
    <nav style={s.nav}>
      <Link to="/dashboard" style={s.navTitle}>Resume Analyzer</Link>
      {token && <button style={s.navBtn} onClick={logout}>Logout</button>}
    </nav>
  );
}

function RequireAuth({ children }) {
  const token = localStorage.getItem("idToken");
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-otp" element={<VerifyOTP />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<RequireAuth><ResumeUpload /></RequireAuth>} />
        <Route path="/results/:resultId" element={<RequireAuth><ReportView /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
