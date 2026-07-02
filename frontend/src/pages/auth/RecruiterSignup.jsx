import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import api from '../../api'

const COMPANY_SIZES = ['1–10', '11–50', '51–200', '201–500', '500+']
const DOMAINS = ['Engineering', 'Product', 'Design', 'Data / ML', 'Sales', 'Marketing', 'Finance', 'Operations', 'HR / People', 'Legal']

const STEPS = ['Account', 'Company', 'Hiring focus']

export default function RecruiterSignup() {
  const [step, setStep]       = useState(0)
  const [loading, setLoading] = useState(false)
  const { login }  = useAuth()
  const { toast }  = useToast()
  const navigate   = useNavigate()

  const [form, setForm] = useState({
    email: '', password: '', name: '',
    org_name: '', company_website: '', company_size: '',
    hiring_role: '', hiring_domains: [],
  })

  const set = (key, val) => setForm(p => ({ ...p, [key]: val }))

  function toggleDomain(d) {
    setForm(p => ({
      ...p,
      hiring_domains: p.hiring_domains.includes(d)
        ? p.hiring_domains.filter(x => x !== d)
        : [...p.hiring_domains, d],
    }))
  }

  async function handleSubmit() {
    setLoading(true)
    try {
      const data = await api.registerRecruiter({
        ...form,
        hiring_domains: form.hiring_domains.length ? form.hiring_domains : undefined,
      })
      login(data)
      navigate('/recruiter/dashboard', { replace: true })
    } catch (err) {
      toast(err.response?.data?.detail || 'Registration failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  function nextStep(e) {
    e.preventDefault()
    if (step < STEPS.length - 1) setStep(s => s + 1)
    else handleSubmit()
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <Link to="/" className="text-white font-semibold text-sm tracking-tight">ResumeIQ</Link>
          <h1 className="text-white text-2xl font-semibold mt-6 mb-1">Set up your hiring team</h1>
          <p className="text-zinc-500 text-sm">
            Already have an account? <Link to="/login" className="text-indigo-400 hover:text-indigo-300">Sign in</Link>
          </p>
        </div>

        <div className="flex gap-1.5 mb-8">
          {STEPS.map((s, i) => (
            <div key={s} className="flex-1 flex flex-col gap-1.5">
              <div className={`h-0.5 rounded-full transition-colors ${i <= step ? 'bg-violet-500' : 'bg-zinc-800'}`} />
              <span className={`text-xs ${i === step ? 'text-violet-400' : i < step ? 'text-zinc-500' : 'text-zinc-700'}`}>{s}</span>
            </div>
          ))}
        </div>

        <form onSubmit={nextStep} className="space-y-4">
          {step === 0 && (
            <>
              <Field label="Your name" id="name" required value={form.name} onChange={e => set('name', e.target.value)} placeholder="Jordan Lee" />
              <Field label="Work email" id="email" type="email" required value={form.email} onChange={e => set('email', e.target.value)} placeholder="jordan@company.com" />
              <Field label="Password" id="pw" type="password" required minLength={8} value={form.password} onChange={e => set('password', e.target.value)} placeholder="8+ characters" />
            </>
          )}

          {step === 1 && (
            <>
              <Field label="Company name" id="org" required value={form.org_name} onChange={e => set('org_name', e.target.value)} placeholder="Acme Corp" />
              <Field label="Website (optional)" id="web" type="url" value={form.company_website} onChange={e => set('company_website', e.target.value)} placeholder="https://acme.com" />
              <div>
                <label className="block text-sm text-zinc-300 mb-2">Company size</label>
                <div className="flex flex-wrap gap-2">
                  {COMPANY_SIZES.map(s => (
                    <button key={s} type="button" onClick={() => set('company_size', s)}
                      className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                        form.company_size === s
                          ? 'bg-violet-600 border-violet-600 text-white'
                          : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-500'
                      }`}>{s}</button>
                  ))}
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <Field label="Your role / title" id="hrole" value={form.hiring_role} onChange={e => set('hiring_role', e.target.value)} placeholder="Engineering Manager" />
              <div>
                <label className="block text-sm text-zinc-300 mb-2">Teams you hire for</label>
                <div className="flex flex-wrap gap-2">
                  {DOMAINS.map(d => (
                    <button key={d} type="button" onClick={() => toggleDomain(d)}
                      className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                        form.hiring_domains.includes(d)
                          ? 'bg-violet-600 border-violet-600 text-white'
                          : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-500'
                      }`}>{d}</button>
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="flex gap-3 pt-2">
            {step > 0 && (
              <button type="button" onClick={() => setStep(s => s - 1)}
                className="flex-1 py-2.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors">
                Back
              </button>
            )}
            <button type="submit" disabled={loading}
              className={`flex-1 py-2.5 rounded-lg text-white text-sm font-medium transition-colors disabled:opacity-50 ${
                step < 2 ? 'bg-zinc-700 hover:bg-zinc-600' : 'bg-violet-600 hover:bg-violet-500'
              }`}>
              {step < STEPS.length - 1 ? 'Continue' : (loading ? 'Creating account…' : 'Create account')}
            </button>
          </div>
        </form>

        <p className="mt-4 text-center text-zinc-600 text-xs">
          Looking for a job?{' '}
          <Link to="/signup/candidate" className="text-zinc-500 hover:text-zinc-300 transition-colors">
            Candidate signup
          </Link>
        </p>
      </div>
    </div>
  )
}

function Field({ label, id, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm text-zinc-300 mb-1.5">{label}</label>
      <input
        id={id}
        {...props}
        className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
      />
    </div>
  )
}
