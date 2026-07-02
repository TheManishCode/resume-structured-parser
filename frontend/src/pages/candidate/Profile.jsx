import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../../api'
import { useToast } from '../../context/ToastContext'
import { useAuth } from '../../context/AuthContext'

const EXP_LEVELS = ['Entry-level', 'Mid-level', 'Senior', 'Lead / Staff', 'Executive']
const JOB_TYPES  = ['Full-time', 'Part-time', 'Contract', 'Freelance', 'Remote', 'Hybrid']

function PageHeader({ title }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
    </div>
  )
}

export default function CandidateProfile() {
  const { toast }        = useToast()
  const { updateProfile } = useAuth()
  const [saving, setSaving] = useState(false)
  const [skillInput, setSkillInput] = useState('')

  const { data: profile, refetch } = useQuery({
    queryKey: ['candidate-profile'],
    queryFn:  () => api.getCandidateProfile(),
  })

  const [form, setForm] = useState(null)
  useEffect(() => { if (profile) setForm({ ...profile }) }, [profile])

  const set = (key, val) => setForm(p => ({ ...p, [key]: val }))

  function toggleArr(key, val) {
    setForm(p => ({
      ...p,
      [key]: (p[key] || []).includes(val)
        ? p[key].filter(x => x !== val)
        : [...(p[key] || []), val],
    }))
  }

  function addSkill(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      const s = skillInput.trim().replace(/,$/, '')
      if (s && !(form.skills || []).includes(s)) set('skills', [...(form.skills || []), s])
      setSkillInput('')
    }
  }

  function removeSkill(s) { set('skills', (form.skills || []).filter(x => x !== s)) }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await api.updateCandidateProfile({
        name: form.name, phone: form.phone, location: form.location,
        target_roles: form.target_roles, experience_level: form.experience_level,
        job_type_pref: form.job_type_pref, skills: form.skills,
        visibility: form.visibility,
      })
      updateProfile({ name: updated.name })
      refetch()
      toast('Profile saved', 'success')
    } catch {
      toast('Failed to save profile', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!form) return (
    <div className="flex flex-col h-full">
      <PageHeader title="Profile" />
      <div className="flex-1 animate-pulse p-6 space-y-4">
        {[120,80,80].map((h,i) => <div key={i} className={`h-${h/4} bg-zinc-200 rounded-xl`} style={{height: h}} />)}
      </div>
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Profile" />
      <form onSubmit={handleSave} className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-6 space-y-6">

          {/* Identity */}
          <Section title="Identity">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Full name" value={form.name || ''} onChange={e => set('name', e.target.value)} placeholder="Alex Johnson" />
              <Field label="Email" value={form.email || ''} disabled />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Phone" value={form.phone || ''} onChange={e => set('phone', e.target.value)} placeholder="+1 555 000 0000" />
              <Field label="Location" value={form.location || ''} onChange={e => set('location', e.target.value)} placeholder="San Francisco, CA" />
            </div>
          </Section>

          {/* Job preferences */}
          <Section title="Job preferences">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-2">Experience level</label>
              <div className="flex flex-wrap gap-2">
                {EXP_LEVELS.map(l => (
                  <button key={l} type="button" onClick={() => set('experience_level', l)}
                    className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                      form.experience_level === l
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'
                    }`}>{l}</button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-2">Job type</label>
              <div className="flex flex-wrap gap-2">
                {JOB_TYPES.map(t => (
                  <button key={t} type="button" onClick={() => toggleArr('job_type_pref', t)}
                    className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                      (form.job_type_pref || []).includes(t)
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'
                    }`}>{t}</button>
                ))}
              </div>
            </div>
          </Section>

          {/* Skills */}
          <Section title="Skills">
            <div className="bg-white border border-zinc-200 rounded-lg p-3 min-h-[80px] focus-within:ring-2 focus-within:ring-indigo-500 transition">
              <div className="flex flex-wrap gap-1.5 mb-2">
                {(form.skills || []).map(s => (
                  <span key={s} className="flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2 py-0.5 rounded border border-indigo-100">
                    {s}
                    <button type="button" onClick={() => removeSkill(s)} className="opacity-50 hover:opacity-100 text-base leading-none">&times;</button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={skillInput}
                onChange={e => setSkillInput(e.target.value)}
                onKeyDown={addSkill}
                className="text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none w-full"
                placeholder="Type a skill and press Enter…"
              />
            </div>
          </Section>

          {/* Visibility */}
          <Section title="Visibility">
            <label className="flex items-center gap-3 cursor-pointer">
              <button
                type="button"
                onClick={() => set('visibility', !form.visibility)}
                className={`relative w-10 h-5.5 rounded-full transition-colors ${form.visibility ? 'bg-indigo-600' : 'bg-zinc-300'}`}
                style={{ height: 22, padding: 0 }}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.visibility ? 'translate-x-[18px]' : ''}`} />
              </button>
              <span className="text-sm text-zinc-700">
                {form.visibility ? 'Profile visible to recruiters' : 'Profile hidden from recruiters'}
              </span>
            </label>
          </Section>

          <div className="pt-2 pb-8">
            <button type="submit" disabled={saving}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors">
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-5 space-y-4">
      <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">{title}</h2>
      {children}
    </div>
  )
}

function Field({ label, ...props }) {
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-600 mb-1.5">{label}</label>
      <input
        {...props}
        className="w-full bg-white border border-zinc-200 rounded-lg px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-zinc-50 disabled:text-zinc-500 transition"
      />
    </div>
  )
}
