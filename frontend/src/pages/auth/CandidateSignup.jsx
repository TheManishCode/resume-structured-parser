import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import api from '../../api'

const EXP_LEVELS = ['Entry-level', 'Mid-level', 'Senior', 'Lead / Staff', 'Executive']
const JOB_TYPES  = ['Full-time', 'Part-time', 'Contract', 'Freelance', 'Remote', 'Hybrid']

const STEPS = ['Account', 'Location & role', 'Skills']

export default function CandidateSignup() {
  const [step, setStep]         = useState(0)
  const [loading, setLoading]   = useState(false)
  const [skillInput, setSkillInput] = useState('')
  const { login }  = useAuth()
  const { toast }  = useToast()
  const navigate   = useNavigate()

  const [form, setForm] = useState({
    email: '', password: '', name: '',
    location: '', phone: '',
    experience_level: '', target_roles: [], job_type_pref: [],
    skills: [],
  })

  const set = (key, val) => setForm(p => ({ ...p, [key]: val }))

  function toggleArr(key, val) {
    setForm(p => ({
      ...p,
      [key]: p[key].includes(val) ? p[key].filter(x => x !== val) : [...p[key], val],
    }))
  }

  function addSkill(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      const s = skillInput.trim().replace(/,$/, '')
      if (s && !form.skills.includes(s)) set('skills', [...form.skills, s])
      setSkillInput('')
    }
  }

  function removeSkill(s) { set('skills', form.skills.filter(x => x !== s)) }

  async function handleSubmit() {
    setLoading(true)
    try {
      const data = await api.registerCandidate({
        ...form,
        target_roles: form.target_roles.length ? form.target_roles : undefined,
        job_type_pref: form.job_type_pref.length ? form.job_type_pref : undefined,
        skills: form.skills.length ? form.skills : undefined,
      })
      login(data)
      navigate('/candidate/dashboard', { replace: true })
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
        {/* Header */}
        <div className="mb-8">
          <Link to="/" className="text-white font-semibold text-sm tracking-tight">ResumeIQ</Link>
          <h1 className="text-white text-2xl font-semibold mt-6 mb-1">Create your account</h1>
          <p className="text-zinc-500 text-sm">
            Already have one? <Link to="/login" className="text-indigo-400 hover:text-indigo-300">Sign in</Link>
          </p>
        </div>

        {/* Step bar */}
        <div className="flex gap-1.5 mb-8">
          {STEPS.map((s, i) => (
            <div key={s} className="flex-1 flex flex-col gap-1.5">
              <div className={`h-0.5 rounded-full transition-colors ${i <= step ? 'bg-indigo-500' : 'bg-zinc-800'}`} />
              <span className={`text-xs ${i === step ? 'text-indigo-400' : i < step ? 'text-zinc-500' : 'text-zinc-700'}`}>{s}</span>
            </div>
          ))}
        </div>

        <form onSubmit={nextStep} className="space-y-4">
          {step === 0 && (
            <>
              <Field label="Full name" id="name" type="text" required value={form.name} onChange={e => set('name', e.target.value)} placeholder="Alex Johnson" />
              <Field label="Email" id="email" type="email" required value={form.email} onChange={e => set('email', e.target.value)} placeholder="you@example.com" />
              <Field label="Password" id="pw" type="password" required value={form.password} onChange={e => set('password', e.target.value)} placeholder="8+ characters" minLength={8} />
            </>
          )}

          {step === 1 && (
            <>
              <Field label="Location" id="loc" type="text" value={form.location} onChange={e => set('location', e.target.value)} placeholder="San Francisco, CA" />
              <Field label="Phone (optional)" id="phone" type="tel" value={form.phone} onChange={e => set('phone', e.target.value)} placeholder="+1 555 000 0000" />

              <div>
                <label className="block text-sm text-zinc-300 mb-2">Experience level</label>
                <div className="flex flex-wrap gap-2">
                  {EXP_LEVELS.map(l => (
                    <button key={l} type="button" onClick={() => set('experience_level', l)}
                      className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                        form.experience_level === l
                          ? 'bg-indigo-600 border-indigo-600 text-white'
                          : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                      }`}>{l}</button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm text-zinc-300 mb-2">Job type preference</label>
                <div className="flex flex-wrap gap-2">
                  {JOB_TYPES.map(t => (
                    <button key={t} type="button" onClick={() => toggleArr('job_type_pref', t)}
                      className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                        form.job_type_pref.includes(t)
                          ? 'bg-indigo-600 border-indigo-600 text-white'
                          : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                      }`}>{t}</button>
                  ))}
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <div>
              <label className="block text-sm text-zinc-300 mb-2">
                Skills <span className="text-zinc-600 font-normal">— type and press Enter or comma</span>
              </label>
              <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-3 min-h-[80px] focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition">
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {form.skills.map(s => (
                    <span key={s} className="flex items-center gap-1 bg-indigo-600/20 text-indigo-300 text-xs px-2 py-0.5 rounded">
                      {s}
                      <button type="button" onClick={() => removeSkill(s)} className="opacity-60 hover:opacity-100">×</button>
                    </span>
                  ))}
                </div>
                <input
                  type="text"
                  value={skillInput}
                  onChange={e => setSkillInput(e.target.value)}
                  onKeyDown={addSkill}
                  className="bg-transparent text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none w-full"
                  placeholder="Python, React, SQL…"
                />
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            {step > 0 && (
              <button type="button" onClick={() => setStep(s => s - 1)}
                className="flex-1 py-2.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors">
                Back
              </button>
            )}
            <button type="submit" disabled={loading}
              className="flex-1 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors">
              {step < STEPS.length - 1 ? 'Continue' : (loading ? 'Creating account…' : 'Create account')}
            </button>
          </div>
        </form>

        <p className="mt-4 text-center text-zinc-600 text-xs">
          Are you hiring?{' '}
          <Link to="/signup/recruiter" className="text-zinc-500 hover:text-zinc-300 transition-colors">
            Create a recruiter account
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
        className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
      />
    </div>
  )
}
