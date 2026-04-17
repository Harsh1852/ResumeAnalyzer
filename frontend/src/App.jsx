import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, Link, useNavigate } from "react-router-dom";
import Register from "./components/Auth/Register";
import VerifyOTP from "./components/Auth/VerifyOTP";
import Login from "./components/Auth/Login";
import ForgotPassword from "./components/Auth/ForgotPassword";
import ResetPassword from "./components/Auth/ResetPassword";
import Profile from "./components/Auth/Profile";
import ResumeUpload from "./components/Resume/ResumeUpload";
import ReportView from "./components/Report/ReportView";
const JobDetail = lazy(() => import("./components/Jobs/JobDetail"));
const TailoredResumeEditor = lazy(() => import("./components/Jobs/TailoredResumeEditor"));

const PageFallback = () => (
  <div style={{ textAlign: "center", padding: 80, color: "#64748b" }}>Loading…</div>
);

function getUserInfo() {
  const token = localStorage.getItem("idToken");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      email: payload.email || "",
      name: payload.name || payload["cognito:username"] || "",
    };
  } catch { return null; }
}

function Nav() {
  const navigate = useNavigate();
  const token = localStorage.getItem("idToken");
  const user = token ? getUserInfo() : null;

  function logout() {
    localStorage.clear();
    navigate("/login");
  }

  const initials = user?.name
    ? user.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : user?.email?.[0]?.toUpperCase() || "U";

  const firstName = user?.name?.split(" ")[0] || user?.email?.split("@")[0] || "";

  return (
    <nav className="no-print" style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 28px", height: 62,
      background: "linear-gradient(90deg,#1e3a8a,#1d4ed8)",
      boxShadow: "0 2px 10px rgba(0,0,0,.2)",
    }}>
      {/* Brand */}
      <Link to="/dashboard" style={{ textDecoration: "none" }}>
        <span style={{ fontWeight: 700, fontSize: 18, color: "#fff", letterSpacing: "-0.2px" }}>
          Resume Analyzer
        </span>
      </Link>

      {/* User section */}
      {user && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* User pill — links to profile */}
          <Link to="/profile" style={{ textDecoration: "none" }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 9,
              background: "rgba(255,255,255,.12)", border: "1px solid rgba(255,255,255,.2)",
              borderRadius: 40, padding: "5px 14px 5px 6px", cursor: "pointer",
              transition: "background .15s",
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,.22)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "rgba(255,255,255,.12)"}
            >
              <div style={{
                width: 30, height: 30, borderRadius: "50%",
                background: "rgba(255,255,255,.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontWeight: 700, fontSize: 12, color: "#fff", flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{firstName}</div>
            </div>
          </Link>

          {/* Sign out */}
          <button
            onClick={logout}
            style={{
              background: "rgba(255,255,255,.12)", border: "1px solid rgba(255,255,255,.25)",
              color: "#fff", padding: "7px 16px", borderRadius: 8,
              cursor: "pointer", fontSize: 13, fontWeight: 500, transition: "all .15s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,.28)"; e.currentTarget.style.borderColor = "rgba(255,255,255,.5)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,.12)"; e.currentTarget.style.borderColor = "rgba(255,255,255,.25)"; }}
          >
            Sign out
          </button>
        </div>
      )}
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
        <Route path="/jobs/:jobId" element={<RequireAuth><Suspense fallback={<PageFallback />}><JobDetail /></Suspense></RequireAuth>} />
        <Route path="/tailored-resumes/:resumeId" element={<RequireAuth><Suspense fallback={<PageFallback />}><TailoredResumeEditor /></Suspense></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
      </Routes>
    </BrowserRouter>
  );
}
