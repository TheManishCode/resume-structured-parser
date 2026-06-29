import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import Login         from './pages/Login'
import RecruiterDash from './pages/RecruiterDash'
import JobDetail     from './pages/JobDetail'
import CandidateDash from './pages/CandidateDash'
import './index.css'

const qc = new QueryClient()

function PrivateRoute({ children, role }) {
  const token = localStorage.getItem('token')
  const userRole = localStorage.getItem('role')
  if (!token) return <Navigate to="/login" replace />
  if (role && userRole !== role) return <Navigate to="/login" replace />
  return children
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/recruiter" element={
            <PrivateRoute role="recruiter"><RecruiterDash /></PrivateRoute>
          } />
          <Route path="/recruiter/jobs/:jobId" element={
            <PrivateRoute role="recruiter"><JobDetail /></PrivateRoute>
          } />
          <Route path="/candidate" element={
            <PrivateRoute role="candidate"><CandidateDash /></PrivateRoute>
          } />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
