import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import api from '../../api'

export default function Login() {
  const [role, setRole]         = useState('candidate')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const { login }  = useAuth()
  const { toast }  = useToast()
  const navigate   = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await api.login(email, password, role)
      login(data)
      navigate(role === 'candidate' ? '/candidate/dashboard' : '/recruiter/dashboard', { replace: true })
    } catch (err) {
      toast(err.response?.data?.detail || 'Invalid credentials', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex">
      {/* Left panel */}
      <div className="hidden lg:flex w-1/2 flex-col justify-between p-12 bg-zinc-900 border-r border-zinc-800">
        <div>
          <span className="text-white font-semibold text-lg tracking-tight">ResumeIQ</span>
        </div>
        <div>
          <p className="text-zinc-400 text-sm mb-8">Trusted by 2,400+ job seekers and hiring teams</p>
          <blockquote className="text-zinc-200 text-xl font-light leading-relaxed">
            "I went from 12% to 78% ATS score in one session. The keyword analysis was surgical."
          </blockquote>
          <p className="mt-4 text-zinc-500 text-sm">Priya S., Product Manager</p>
        </div>
        <p className="text-zinc-600 text-xs">AI-powered resume screening for candidates and teams.</p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <h1 className="text-white text-2xl font-semibold mb-1">Sign in</h1>
          <p className="text-zinc-500 text-sm mb-8">
            Don't have an account?{' '}
            <Link to="/signup/candidate" className="text-indigo-400 hover:text-indigo-300 transition-colors">
              Get started free
            </Link>
          </p>

          {/* Role toggle */}
          <div className="flex mb-6 bg-zinc-900 p-1 rounded-lg border border-zinc-800">
            {['candidate', 'recruiter'].map(r => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-all ${
                  role === r
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {r.charAt(0).toUpperCase() + r.slice(1)}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm text-zinc-300 mb-1.5">Email</label>
              <input
                id="email" type="email" required autoComplete="email"
                value={email} onChange={e => setEmail(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <div className="flex justify-between mb-1.5">
                <label htmlFor="pw" className="text-sm text-zinc-300">Password</label>
                <Link to="/forgot-password" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                  Forgot?
                </Link>
              </div>
              <input
                id="pw" type="password" required autoComplete="current-password"
                value={password} onChange={e => setPassword(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-950"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-6 text-center text-zinc-600 text-xs">
            {role === 'recruiter'
              ? <><Link to="/signup/recruiter" className="text-zinc-400 hover:text-white transition-colors">Create recruiter account</Link></>
              : <><Link to="/signup/candidate" className="text-zinc-400 hover:text-white transition-colors">Create candidate account</Link></>
            }
          </p>
        </div>
      </div>
    </div>
  )
}
