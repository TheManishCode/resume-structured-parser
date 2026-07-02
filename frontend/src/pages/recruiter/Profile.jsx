import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../../api'
import { useToast } from '../../context/ToastContext'
import { useAuth } from '../../context/AuthContext'

const COMPANY_SIZES = ['1–10', '11–50', '51–200', '201–500', '500+']
const DOMAINS = ['Engineering', 'Product', 'Design', 'Data / ML', 'Sales', 'Marketing', 'Finance', 'Operations', 'HR / People', 'Legal']

function PageHeader({ title }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
    </div>
  )
}

export default function RecruiterProfile() {
  const { toast }         = useToast()
  const { updateProfile } = useAuth()
  const [saving, setSaving] = useState(false)

  const { data: profile, refetch } = useQuery({
    queryKey: ['recruiter-profile'],
    queryFn:  () => api.getRecruiterProfile(),
  })

  const [form, setForm] = useState(null)
  useEffect(() => { if (profile) setForm({ ...profile }) }, [profile])

  const set = (key, val) => setForm(p => ({ ...p, [key]: val }))

  function toggleDomain(d) {
    setForm(p => ({
      ...p,
      hiring_domains: (p.hiring_domains || []).includes(d)
        ? p.hiring_domains.filter(x => x !== d)
        : [...(p.hiring_domains || []), d],
    }))
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await api.updateRecruiterProfile({
        name: form.name, org_name: form.org_name,
        company_website: form.company_website,
        hiring_role: form.hiring_role,
        hiring_domains: form.hiring_domains,
        company_size: form.company_size,
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
      <PageHeader title="Company profile" />
      <div className="flex-1 animate-pulse p-6 space-y-4">
        {[120, 80, 80].map((h, i) => <div key={i} className="bg-zinc-200 rounded-xl" style={{ height: h }} />)}
      </div>
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Company profile" />
      <form onSubmit={handleSave} className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-6 space-y-6">

          <Section title="Your details">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Your name" value={form.name || ''} onChange={e => set('name', e.target.value)} placeholder="Jordan Lee" />
              <Field label="Your title / role" value={form.hiring_role || ''} onChange={e => set('hiring_role', e.target.value)} placeholder="Engineering Manager" />
            </div>
            <Field label="Work email" value={form.email || ''} disabled />
          </Section>

          <Section title="Company">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Company name" value={form.org_name || ''} onChange={e => set('org_name', e.target.value)} placeholder="Acme Corp" />
              <Field label="Website" type="url" value={form.company_website || ''} onChange={e => set('company_website', e.target.value)} placeholder="https://acme.com" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-2">Company size</label>
              <div className="flex flex-wrap gap-2">
                {COMPANY_SIZES.map(s => (
                  <button key={s} type="button" onClick={() => set('company_size', s)}
                    className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                      form.company_size === s
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'
                    }`}>{s}</button>
                ))}
              </div>
            </div>
          </Section>

          <Section title="Hiring focus">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-2">Teams you hire for</label>
              <div className="flex flex-wrap gap-2">
                {DOMAINS.map(d => (
                  <button key={d} type="button" onClick={() => toggleDomain(d)}
                    className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${
                      (form.hiring_domains || []).includes(d)
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400'
                    }`}>{d}</button>
                ))}
              </div>
            </div>
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
