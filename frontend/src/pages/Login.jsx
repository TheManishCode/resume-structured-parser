import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, registerRecruiter, registerCandidate } from '../api'

export default function Login() {
  const nav = useNavigate()
  const [mode,     setMode]     = useState('login')   // 'login' | 'reg-recruiter' | 'reg-candidate'
  const [role,     setRole]     = useState('recruiter')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [org,      setOrg]      = useState('')
  const [error,    setError]    = useState('')

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      let res
      if (mode === 'login') {
        res = await login(email, password, role)
      } else if (mode === 'reg-recruiter') {
        res = await registerRecruiter(email, password, org)
      } else {
        res = await registerCandidate(email, password)
      }
      const { access_token, role: returnedRole } = res.data
      localStorage.setItem('token', access_token)
      localStorage.setItem('role',  returnedRole)
      nav(returnedRole === 'recruiter' ? '/recruiter' : '/candidate')
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow p-8 w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">AI Talent Platform</h1>

        <div className="flex gap-2 mb-6 text-sm">
          {[['login','Login'],['reg-recruiter','Register Recruiter'],['reg-candidate','Register Candidate']].map(
            ([key, label]) => (
              <button key={key} onClick={() => setMode(key)}
                className={`flex-1 py-1.5 rounded-lg border ${mode === key ? 'bg-indigo-600 text-white border-indigo-600' : 'text-gray-600 border-gray-300'}`}>
                {label}
              </button>
            )
          )}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === 'login' && (
            <select value={role} onChange={e => setRole(e.target.value)}
              className="w-full border rounded-lg p-2.5 text-sm">
              <option value="recruiter">Recruiter</option>
              <option value="candidate">Candidate</option>
            </select>
          )}
          {mode === 'reg-recruiter' && (
            <input placeholder="Organisation name" value={org} onChange={e => setOrg(e.target.value)}
              className="w-full border rounded-lg p-2.5 text-sm" required />
          )}
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full border rounded-lg p-2.5 text-sm" required />
          <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full border rounded-lg p-2.5 text-sm" required />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button type="submit" className="w-full bg-indigo-600 text-white rounded-lg py-2.5 font-semibold hover:bg-indigo-700">
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
