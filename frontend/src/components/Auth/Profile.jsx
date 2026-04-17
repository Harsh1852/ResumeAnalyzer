import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword, updateEmail, verifyEmailChange, deleteAccount, forgotPassword, confirmForgotPassword } from "../../services/api";

const s = {
  page: { maxWidth: 600, margin: "40px auto", padding: "0 20px 60px" },
  card: { background: "#fff", borderRadius: 12, padding: "28px 32px", boxShadow: "0 2px 12px rgba(0,0,0,.07)", marginBottom: 20 },
  sectionTitle: { fontSize: 17, fontWeight: 700, margin: "0 0 20px" },
  label: { display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500, color: "#374151" },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 15, outline: "none", marginBottom: 16, boxSizing: "border-box" },
  btn: { padding: "10px 24px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: "pointer" },
  btnOutline: { padding: "10px 24px", background: "none", border: "1px solid #2563eb", color: "#2563eb", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: "pointer" },
  err: { color: "#dc2626", fontSize: 13, marginBottom: 12 },
  ok: { color: "#16a34a", fontSize: 13, marginBottom: 12 },
  divider: { border: "none", borderTop: "1px solid #e5e7eb", margin: "4px 0 20px" },
  backBtn: { background: "none", border: "none", color: "#2563eb", cursor: "pointer", fontSize: 14, padding: 0, marginBottom: 20 },
};

function getUserInfo() {
  const token = localStorage.getItem("idToken");
  if (!token) return { email: "", name: "" };
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      email: payload.email || "",
      name: payload.name || payload["cognito:username"] || "",
    };
  } catch { return { email: "", name: "" }; }
}

export default function Profile() {
  const navigate = useNavigate();
  const user = getUserInfo();

  const [pwdForm, setPwdForm] = useState({ current: "", next: "", confirm: "" });
  const [pwdError, setPwdError] = useState("");
  const [pwdOk, setPwdOk] = useState("");
  const [pwdLoading, setPwdLoading] = useState(false);

  const [resetStep, setResetStep] = useState("idle"); // "idle" | "sent"
  const [resetCode, setResetCode] = useState("");
  const [resetPwd, setResetPwd] = useState({ next: "", confirm: "" });
  const [resetError, setResetError] = useState("");
  const [resetOk, setResetOk] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

  const [emailForm, setEmailForm] = useState({ newEmail: "" });
  const [emailError, setEmailError] = useState("");
  const [emailOk, setEmailOk] = useState("");
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailStep, setEmailStep] = useState("input"); // "input" | "verify"
  const [verifyCode, setVerifyCode] = useState("");

  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showDeleteSection, setShowDeleteSection] = useState(false);

  async function handleChangePassword(e) {
    e.preventDefault();
    setPwdError("");
    setPwdOk("");
    if (pwdForm.next !== pwdForm.confirm) {
      setPwdError("New passwords do not match");
      return;
    }
    if (pwdForm.next.length < 8) {
      setPwdError("Password must be at least 8 characters");
      return;
    }
    setPwdLoading(true);
    try {
      await changePassword(pwdForm.current, pwdForm.next);
      setPwdOk("Password changed successfully");
      setPwdForm({ current: "", next: "", confirm: "" });
    } catch (err) {
      setPwdError(err.response?.data?.error || "Failed to change password");
    } finally {
      setPwdLoading(false);
    }
  }

  async function handleSendResetCode() {
    setResetError("");
    setResetOk("");
    setResetLoading(true);
    try {
      await forgotPassword(user.email);
      setResetOk(`Reset code sent to ${user.email}`);
      setResetStep("sent");
    } catch (err) {
      setResetError(err.response?.data?.error || "Failed to send reset code");
    } finally {
      setResetLoading(false);
    }
  }

  async function handleConfirmReset(e) {
    e.preventDefault();
    setResetError("");
    if (resetPwd.next !== resetPwd.confirm) {
      setResetError("Passwords do not match");
      return;
    }
    if (resetPwd.next.length < 8) {
      setResetError("Password must be at least 8 characters");
      return;
    }
    setResetLoading(true);
    try {
      await confirmForgotPassword(user.email, resetCode.trim(), resetPwd.next);
      localStorage.clear();
      navigate("/login", { state: { message: "Password reset successfully. Please sign in." } });
    } catch (err) {
      setResetError(err.response?.data?.error || "Invalid or expired code");
      setResetLoading(false);
    }
  }

  async function handleSendEmailCode(e) {
    e.preventDefault();
    setEmailError("");
    setEmailOk("");
    if (!emailForm.newEmail) return;
    setEmailLoading(true);
    try {
      await updateEmail(emailForm.newEmail.trim().toLowerCase());
      setEmailOk("Verification code sent to your new email");
      setEmailStep("verify");
    } catch (err) {
      setEmailError(err.response?.data?.error || "Failed to send verification code");
    } finally {
      setEmailLoading(false);
    }
  }

  async function handleVerifyEmail(e) {
    e.preventDefault();
    setEmailError("");
    setEmailLoading(true);
    try {
      await verifyEmailChange(verifyCode.trim());
      localStorage.clear();
      navigate("/login", { state: { verified: true } });
    } catch (err) {
      setEmailError(err.response?.data?.error || "Invalid or expired code");
    } finally {
      setEmailLoading(false);
    }
  }

  async function handleDeleteAccount(e) {
    e.preventDefault();
    setDeleteError("");
    if (deleteConfirm !== user.email) {
      setDeleteError("Email does not match");
      return;
    }
    setDeleteLoading(true);
    try {
      await deleteAccount();
      localStorage.clear();
      navigate("/login");
    } catch (err) {
      setDeleteError(err.response?.data?.error || "Failed to delete account");
      setDeleteLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <button style={s.backBtn} onClick={() => navigate("/dashboard")}>← Back to Dashboard</button>

      <div style={s.card}>
        <h2 style={s.sectionTitle}>Account Info</h2>
        <hr style={s.divider} />
        <div style={{ fontSize: 14, color: "#374151", marginBottom: 8 }}>
          <span style={{ fontWeight: 600 }}>Name: </span>{user.name || "—"}
        </div>
        <div style={{ fontSize: 14, color: "#374151" }}>
          <span style={{ fontWeight: 600 }}>Email: </span>{user.email}
        </div>
      </div>

      <div style={s.card}>
        <h2 style={s.sectionTitle}>Change Password</h2>
        <hr style={s.divider} />
        {pwdError && <p style={s.err}>{pwdError}</p>}
        {pwdOk && <p style={s.ok}>{pwdOk}</p>}
        <form onSubmit={handleChangePassword}>
          <label style={s.label}>Current Password</label>
          <input
            style={s.input}
            type="password"
            placeholder="••••••••"
            required
            value={pwdForm.current}
            onChange={(e) => setPwdForm({ ...pwdForm, current: e.target.value })}
          />
          <label style={s.label}>New Password <span style={{ color: "#9ca3af", fontWeight: 400 }}>(min. 8 chars, upper + lower + digit)</span></label>
          <input
            style={s.input}
            type="password"
            placeholder="••••••••"
            required
            value={pwdForm.next}
            onChange={(e) => setPwdForm({ ...pwdForm, next: e.target.value })}
          />
          <label style={s.label}>Confirm New Password</label>
          <input
            style={s.input}
            type="password"
            placeholder="••••••••"
            required
            value={pwdForm.confirm}
            onChange={(e) => setPwdForm({ ...pwdForm, confirm: e.target.value })}
          />
          <button style={{ ...s.btn, opacity: pwdLoading ? 0.7 : 1 }} type="submit" disabled={pwdLoading}>
            {pwdLoading ? "Saving…" : "Change Password"}
          </button>
        </form>
      </div>

      <div style={s.card}>
        <h2 style={s.sectionTitle}>Reset Password via Email</h2>
        <hr style={s.divider} />
        <p style={{ fontSize: 13, color: "#6b7280", marginTop: -8, marginBottom: 16 }}>
          Don't know your current password? Send a reset code to <strong>{user.email}</strong>.
        </p>
        {resetError && <p style={s.err}>{resetError}</p>}
        {resetOk && <p style={s.ok}>{resetOk}</p>}

        {resetStep === "idle" && (
          <button
            style={{ ...s.btnOutline, opacity: resetLoading ? 0.7 : 1 }}
            onClick={handleSendResetCode}
            disabled={resetLoading}
          >
            {resetLoading ? "Sending…" : "Send Reset Code"}
          </button>
        )}

        {resetStep === "sent" && (
          <form onSubmit={handleConfirmReset}>
            <label style={s.label}>Reset Code</label>
            <input
              style={s.input}
              type="text"
              placeholder="6-digit code"
              required
              value={resetCode}
              onChange={(e) => setResetCode(e.target.value)}
            />
            <label style={s.label}>New Password <span style={{ color: "#9ca3af", fontWeight: 400 }}>(min. 8 chars, upper + lower + digit)</span></label>
            <input
              style={s.input}
              type="password"
              placeholder="••••••••"
              required
              value={resetPwd.next}
              onChange={(e) => setResetPwd({ ...resetPwd, next: e.target.value })}
            />
            <label style={s.label}>Confirm New Password</label>
            <input
              style={s.input}
              type="password"
              placeholder="••••••••"
              required
              value={resetPwd.confirm}
              onChange={(e) => setResetPwd({ ...resetPwd, confirm: e.target.value })}
            />
            <div style={{ display: "flex", gap: 10 }}>
              <button style={{ ...s.btn, opacity: resetLoading ? 0.7 : 1 }} type="submit" disabled={resetLoading}>
                {resetLoading ? "Resetting…" : "Reset Password"}
              </button>
              <button
                type="button"
                style={s.btnOutline}
                onClick={() => { setResetStep("idle"); setResetCode(""); setResetPwd({ next: "", confirm: "" }); setResetError(""); setResetOk(""); }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      <div style={s.card}>
        <h2 style={s.sectionTitle}>Change Email</h2>
        <hr style={s.divider} />
        {emailError && <p style={s.err}>{emailError}</p>}
        {emailOk && <p style={s.ok}>{emailOk}</p>}

        {emailStep === "input" && (
          <form onSubmit={handleSendEmailCode}>
            <label style={s.label}>New Email Address</label>
            <input
              style={s.input}
              type="email"
              placeholder="new@example.com"
              required
              value={emailForm.newEmail}
              onChange={(e) => setEmailForm({ newEmail: e.target.value })}
            />
            <button style={{ ...s.btn, opacity: emailLoading ? 0.7 : 1 }} type="submit" disabled={emailLoading}>
              {emailLoading ? "Sending…" : "Send Verification Code"}
            </button>
          </form>
        )}

        {emailStep === "verify" && (
          <form onSubmit={handleVerifyEmail}>
            <label style={s.label}>Verification Code</label>
            <p style={{ fontSize: 13, color: "#6b7280", marginTop: -10, marginBottom: 12 }}>
              Enter the code sent to <strong>{emailForm.newEmail}</strong>. You will be signed out after verification.
            </p>
            <input
              style={s.input}
              type="text"
              placeholder="6-digit code"
              required
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value)}
            />
            <div style={{ display: "flex", gap: 10 }}>
              <button style={{ ...s.btn, opacity: emailLoading ? 0.7 : 1 }} type="submit" disabled={emailLoading}>
                {emailLoading ? "Verifying…" : "Verify & Update Email"}
              </button>
              <button
                type="button"
                style={s.btnOutline}
                onClick={() => { setEmailStep("input"); setEmailOk(""); setEmailError(""); setVerifyCode(""); }}
              >
                Change Email
              </button>
            </div>
          </form>
        )}
      </div>

      <div style={{ ...s.card, borderLeft: "4px solid #dc2626" }}>
        <h2 style={{ ...s.sectionTitle, color: "#dc2626" }}>Delete Account</h2>
        <hr style={s.divider} />
        {!showDeleteSection ? (
          <>
            <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 16 }}>
              Permanently delete your account and all associated data. This cannot be undone.
            </p>
            <button
              style={{ ...s.btn, background: "none", border: "1px solid #fca5a5", color: "#dc2626" }}
              onClick={() => setShowDeleteSection(true)}
            >
              Delete My Account
            </button>
          </>
        ) : (
          <form onSubmit={handleDeleteAccount}>
            {deleteError && <p style={s.err}>{deleteError}</p>}
            <label style={s.label}>
              Type your email <strong>{user.email}</strong> to confirm
            </label>
            <input
              style={{ ...s.input, borderColor: "#fca5a5" }}
              type="email"
              placeholder={user.email}
              required
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
            />
            <div style={{ display: "flex", gap: 10 }}>
              <button
                style={{ ...s.btn, background: "#dc2626", opacity: deleteLoading ? 0.7 : 1 }}
                type="submit"
                disabled={deleteLoading}
              >
                {deleteLoading ? "Deleting…" : "Confirm Delete"}
              </button>
              <button
                type="button"
                style={s.btnOutline}
                onClick={() => { setShowDeleteSection(false); setDeleteConfirm(""); setDeleteError(""); }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
