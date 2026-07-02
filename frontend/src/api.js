import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const client = axios.create({ baseURL: BASE })

client.interceptors.request.use(cfg => {
  try {
    const auth = localStorage.getItem('atp_auth')
    if (auth) {
      const { token } = JSON.parse(auth)
      if (token) cfg.headers.Authorization = `Bearer ${token}`
    }
  } catch {}
  return cfg
})

function data(r) { return r.data }

// ── Public analyze (no auth required, but sends token if available) ───────────
function analyzeResume(file, jobUrl = '', jobText = '') {
  const fd = new FormData()
  fd.append('file',     file)
  fd.append('job_url',  jobUrl)
  fd.append('job_text', jobText)
  return client.post('/analyze', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data)
}

function checkAts(file) {
  const fd = new FormData()
  fd.append('file', file)
  return client.post('/analyze/ats-check', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data)
}

// ── Auth ──────────────────────────────────────────────────────────────────────
function login(email, password, role) {
  return client.post('/auth/login', { email, password, role }).then(data)
}
function registerCandidate(body) {
  return client.post('/auth/register/candidate', body).then(data)
}
function registerRecruiter(body) {
  return client.post('/auth/register/recruiter', body).then(data)
}

// ── Candidate ─────────────────────────────────────────────────────────────────
function getCandidateProfile() {
  return client.get('/candidate/profile').then(data)
}
function updateCandidateProfile(body) {
  return client.patch('/candidate/profile', body).then(data)
}
function getCandidateDashboard() {
  return client.get('/candidate/dashboard').then(data)
}
function getCandidateAnalytics() {
  return client.get('/candidate/analytics').then(data)
}
function getCandidateHistory(limit = 20, offset = 0) {
  return client.get(`/candidate/history?limit=${limit}&offset=${offset}`).then(data)
}

// ── Recruiter ─────────────────────────────────────────────────────────────────
function getRecruiterProfile() {
  return client.get('/recruiter/profile').then(data)
}
function updateRecruiterProfile(body) {
  return client.patch('/recruiter/profile', body).then(data)
}
function getRecruiterDashboard() {
  return client.get('/recruiter/dashboard').then(data)
}
function getRecruiterAnalytics() {
  return client.get('/recruiter/analytics').then(data)
}
function getJobAnalytics(jobId) {
  return client.get(`/recruiter/jobs/${jobId}/analytics`).then(data)
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
function createJob(title, description) {
  return client.post('/jobs', { title, description }).then(data)
}
function listJobs() {
  return client.get('/jobs').then(data)
}
function getJob(id) {
  return client.get(`/jobs/${id}`).then(data)
}
function rankJob(id, limit = 20) {
  return client.get(`/jobs/${id}/rank?limit=${limit}`).then(data)
}
function scoreResume(jobId, resumeId, forceCloud = false) {
  return client.post(`/jobs/${jobId}/score`, { resume_id: resumeId, force_cloud: forceCloud }).then(data)
}

// ── Resumes ───────────────────────────────────────────────────────────────────
function uploadResume(file) {
  const fd = new FormData()
  fd.append('file', file)
  return client.post('/resumes/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(data)
}
function myResumes() {
  return client.get('/resumes/me').then(data)
}

// ── Scores ────────────────────────────────────────────────────────────────────
function myScores() {
  return client.get('/scores/candidate/me').then(data)
}
function getScore(id) {
  return client.get(`/scores/${id}`).then(data)
}

const api = {
  analyzeResume, checkAts,
  login, registerCandidate, registerRecruiter,
  getCandidateProfile, updateCandidateProfile, getCandidateDashboard, getCandidateAnalytics, getCandidateHistory,
  getRecruiterProfile, updateRecruiterProfile, getRecruiterDashboard, getRecruiterAnalytics, getJobAnalytics,
  createJob, listJobs, getJob, rankJob, scoreResume,
  uploadResume, myResumes, myScores, getScore,
}

export default api
// Named exports for backward compatibility with any existing imports
export { analyzeResume, login, registerCandidate, registerRecruiter, listJobs, getJob, uploadResume, myResumes, myScores }
