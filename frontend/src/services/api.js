import axios from "axios";

const AUTH_API = import.meta.env.VITE_AUTH_API_URL;
const APP_API = import.meta.env.VITE_APP_API_URL;
const RESULTS_API = import.meta.env.VITE_RESULTS_API_URL;
const JOBS_API = import.meta.env.VITE_JOBS_API_URL;
const APPLICATIONS_API = import.meta.env.VITE_APPLICATIONS_API_URL;

function authHeaders() {
  const token = localStorage.getItem("idToken");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const register = (email, password, name) =>
  axios.post(`${AUTH_API}/auth/register`, { email, password, name }).then((r) => r.data);

export const verifyOTP = (email, code) =>
  axios.post(`${AUTH_API}/auth/verify`, { email, code }).then((r) => r.data);

export const resendOTP = (email) =>
  axios.post(`${AUTH_API}/auth/resend-otp`, { email }).then((r) => r.data);

export const login = (email, password) =>
  axios.post(`${AUTH_API}/auth/login`, { email, password }).then((r) => r.data);

export const refreshToken = (refreshToken) =>
  axios.post(`${AUTH_API}/auth/refresh`, { refreshToken }).then((r) => r.data);

export const forgotPassword = (email) =>
  axios.post(`${AUTH_API}/auth/forgot-password`, { email }).then((r) => r.data);

export const confirmForgotPassword = (email, code, newPassword) =>
  axios.post(`${AUTH_API}/auth/confirm-forgot-password`, { email, code, newPassword }).then((r) => r.data);

function accessHeaders() {
  const token = localStorage.getItem("accessToken");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const changePassword = (currentPassword, newPassword) =>
  axios.post(`${AUTH_API}/auth/change-password`, { currentPassword, newPassword }, { headers: accessHeaders() }).then((r) => r.data);

export const updateEmail = (newEmail) =>
  axios.post(`${AUTH_API}/auth/update-email`, { newEmail }, { headers: accessHeaders() }).then((r) => r.data);

export const verifyEmailChange = (code) =>
  axios.post(`${AUTH_API}/auth/verify-email-change`, { code }, { headers: accessHeaders() }).then((r) => r.data);

export const deleteAccount = () =>
  axios.post(`${AUTH_API}/auth/delete-account`, {}, { headers: accessHeaders() }).then((r) => r.data);

// ── Uploads ───────────────────────────────────────────────────────────────────
export const getPresignedUrl = (fileName, contentType) =>
  axios
    .post(`${APP_API}/uploads/presigned-url`, { fileName, contentType }, { headers: authHeaders() })
    .then((r) => r.data);

export const uploadToS3 = (presignedUrl, file) =>
  axios.put(presignedUrl, file, {
    headers: { "Content-Type": file.type },
    onUploadProgress: undefined,
  });

export const confirmUpload = (uploadId) =>
  axios
    .post(`${APP_API}/uploads/confirm`, { uploadId }, { headers: authHeaders() })
    .then((r) => r.data);

export const listUploads = () =>
  axios.get(`${APP_API}/uploads`, { headers: authHeaders() }).then((r) => r.data);

export const getUpload = (uploadId) =>
  axios.get(`${APP_API}/uploads/${uploadId}`, { headers: authHeaders() }).then((r) => r.data);

export const getResumeViewUrl = (uploadId) =>
  axios.get(`${APP_API}/uploads/${uploadId}/view-url`, { headers: authHeaders() }).then((r) => r.data);

export const deleteUpload = (uploadId) =>
  axios.delete(`${APP_API}/uploads/${uploadId}`, { headers: authHeaders() }).then((r) => r.data);

export const deleteResult = (resultId) =>
  axios.delete(`${RESULTS_API}/results/${resultId}`, { headers: authHeaders() }).then((r) => r.data);

// ── Results ───────────────────────────────────────────────────────────────────
export const getResults = (uploadId) => {
  const params = uploadId ? { uploadId } : {};
  return axios
    .get(`${RESULTS_API}/results`, { headers: authHeaders(), params })
    .then((r) => r.data);
};

export const getResult = (resultId) =>
  axios.get(`${RESULTS_API}/results/${resultId}`, { headers: authHeaders() }).then((r) => r.data);

// ── Jobs ──────────────────────────────────────────────────────────────────────
export const listJobs = (resultId) =>
  axios
    .get(`${JOBS_API}/jobs`, { headers: authHeaders(), params: { resultId } })
    .then((r) => r.data);

export const searchJobs = (resultId, country) =>
  axios
    .post(`${JOBS_API}/jobs/search`, { resultId, country }, { headers: authHeaders() })
    .then((r) => r.data);

export const getJob = (jobId) =>
  axios.get(`${JOBS_API}/jobs/${jobId}`, { headers: authHeaders() }).then((r) => r.data);

export const fetchCoursesForJob = (jobId) =>
  axios
    .post(`${JOBS_API}/jobs/${jobId}/courses`, {}, { headers: authHeaders() })
    .then((r) => r.data);

export const createTailoredResume = (jobId, resumeText) =>
  axios
    .post(`${JOBS_API}/jobs/${jobId}/tailored-resume`, { resumeText }, { headers: authHeaders() })
    .then((r) => r.data);

export const getTailoredResume = (resumeId) =>
  axios
    .get(`${JOBS_API}/tailored-resumes/${resumeId}`, { headers: authHeaders() })
    .then((r) => r.data);

export const saveTailoredResume = (resumeId, markdown) =>
  axios
    .put(`${JOBS_API}/tailored-resumes/${resumeId}`, { markdown }, { headers: authHeaders() })
    .then((r) => r.data);

// ── Applications / Job Tracker ────────────────────────────────────────────────
export const APPLICATION_STATUSES = [
  "Wishlist",
  "Applied",
  "Phone Screen",
  "Technical Interview",
  "Onsite",
  "Offer",
  "Rejected",
  "Ghosted",
];

export const INTERVIEW_OUTCOMES = ["PENDING", "PASSED", "FAILED", "NO_SHOW", "RESCHEDULED"];

export const listApplications = (status) => {
  const params = status ? { status } : {};
  return axios
    .get(`${APPLICATIONS_API}/applications`, { headers: authHeaders(), params })
    .then((r) => r.data);
};

export const getApplicationStats = () =>
  axios
    .get(`${APPLICATIONS_API}/applications/stats`, { headers: authHeaders() })
    .then((r) => r.data);

export const getApplication = (applicationId) =>
  axios
    .get(`${APPLICATIONS_API}/applications/${applicationId}`, { headers: authHeaders() })
    .then((r) => r.data);

export const createApplication = (payload) =>
  axios
    .post(`${APPLICATIONS_API}/applications`, payload, { headers: authHeaders() })
    .then((r) => r.data);

export const updateApplication = (applicationId, patch) =>
  axios
    .patch(`${APPLICATIONS_API}/applications/${applicationId}`, patch, { headers: authHeaders() })
    .then((r) => r.data);

export const deleteApplication = (applicationId) =>
  axios
    .delete(`${APPLICATIONS_API}/applications/${applicationId}`, { headers: authHeaders() })
    .then((r) => r.data);

export const addInterviewRound = (applicationId, round) =>
  axios
    .post(`${APPLICATIONS_API}/applications/${applicationId}/rounds`, round, { headers: authHeaders() })
    .then((r) => r.data);

export const updateInterviewRound = (applicationId, roundId, patch) =>
  axios
    .patch(`${APPLICATIONS_API}/applications/${applicationId}/rounds/${roundId}`, patch, { headers: authHeaders() })
    .then((r) => r.data);

export const deleteInterviewRound = (applicationId, roundId) =>
  axios
    .delete(`${APPLICATIONS_API}/applications/${applicationId}/rounds/${roundId}`, { headers: authHeaders() })
    .then((r) => r.data);
