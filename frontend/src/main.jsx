import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AuthProvider, useAuth }   from './context/AuthContext'
import { ToastProvider }           from './context/ToastContext'

// Layouts
import CandidateLayout from './components/layouts/CandidateLayout'
import RecruiterLayout from './components/layouts/RecruiterLayout'

// Auth pages
import Login          from './pages/auth/Login'
import CandidateSignup from './pages/auth/CandidateSignup'
import RecruiterSignup from './pages/auth/RecruiterSignup'

// Public
import Analyze from './pages/Analyze'

// Candidate pages
import CandidateDashboard from './pages/candidate/Dashboard'
import CandidateProfile   from './pages/candidate/Profile'
import CandidateHistory   from './pages/candidate/History'
import CandidateSettings  from './pages/candidate/Settings'

// Recruiter pages
import RecruiterDashboard from './pages/recruiter/Dashboard'
import RecruiterProfile   from './pages/recruiter/Profile'
import RecruiterJobs      from './pages/recruiter/Jobs'
import RecruiterAnalytics from './pages/recruiter/Analytics'
import RecruiterSettings  from './pages/recruiter/Settings'

// Legacy page imports (kept for backward compat while still present)
import './index.css'

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

function RequireAuth({ role, children }) {
  const { isAuthenticated, auth } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (role && auth?.role !== role) {
    return <Navigate to={auth?.role === 'candidate' ? '/candidate/dashboard' : '/recruiter/dashboard'} replace />
  }
  return children
}

function RootRedirect() {
  const { isAuthenticated, auth } = useAuth()
  if (isAuthenticated) {
    return <Navigate to={auth.role === 'candidate' ? '/candidate/dashboard' : '/recruiter/dashboard'} replace />
  }
  return <Analyze />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              {/* Public */}
              <Route path="/"        element={<RootRedirect />} />
              <Route path="/analyze" element={<Analyze />} />

              {/* Auth */}
              <Route path="/login"            element={<Login />} />
              <Route path="/signup/candidate" element={<CandidateSignup />} />
              <Route path="/signup/recruiter" element={<RecruiterSignup />} />
              <Route path="/forgot-password"  element={<Login />} />

              {/* Candidate — sidebar layout */}
              <Route path="/candidate" element={
                <RequireAuth role="candidate"><CandidateLayout /></RequireAuth>
              }>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<CandidateDashboard />} />
                <Route path="analyze"   element={<Analyze embedded />} />
                <Route path="history"   element={<CandidateHistory />} />
                <Route path="profile"   element={<CandidateProfile />} />
                <Route path="settings"  element={<CandidateSettings />} />
              </Route>

              {/* Recruiter — sidebar layout */}
              <Route path="/recruiter" element={
                <RequireAuth role="recruiter"><RecruiterLayout /></RequireAuth>
              }>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<RecruiterDashboard />} />
                <Route path="jobs"      element={<RecruiterJobs />} />
                <Route path="analytics" element={<RecruiterAnalytics />} />
                <Route path="profile"   element={<RecruiterProfile />} />
                <Route path="settings"  element={<RecruiterSettings />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
