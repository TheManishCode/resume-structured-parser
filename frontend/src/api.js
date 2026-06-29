import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const client = axios.create({ baseURL: BASE })

client.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auth
export const registerRecruiter = (email, password, org_name) =>
  client.post('/auth/register/recruiter', { email, password, org_name })

export const registerCandidate = (email, password) =>
  client.post('/auth/register/candidate', { email, password })

export const login = (email, password, role) =>
  client.post('/auth/login', { email, password, role })

// Jobs
export const createJob   = (title, description)  => client.post('/jobs', { title, description })
export const listJobs    = ()                     => client.get('/jobs')
export const getJob      = (id)                   => client.get(`/jobs/${id}`)
export const rankJob     = (id, limit = 20)       => client.get(`/jobs/${id}/rank?limit=${limit}`)
export const scoreResume = (jobId, resumeId, forceCloud = false) =>
  client.post(`/jobs/${jobId}/score`, { resume_id: resumeId, force_cloud: forceCloud })

// Resumes
export const uploadResume  = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return client.post('/resumes/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const myResumes = () => client.get('/resumes/me')

// Scores
export const myScores  = () => client.get('/scores/candidate/me')
export const getScore  = (id) => client.get(`/scores/${id}`)
