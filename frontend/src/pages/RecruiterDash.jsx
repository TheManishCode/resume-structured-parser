import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { createJob, listJobs } from '../api'

export default function RecruiterDash() {
  const nav = useNavigate()
  const qc  = useQueryClient()
  const [title, setTitle] = useState('')
  const [desc,  setDesc]  = useState('')
  const [open,  setOpen]  = useState(false)

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn:  () => listJobs().then(r => r.data),
  })

  const createMut = useMutation({
    mutationFn: () => createJob(title, desc),
    onSuccess:  () => { qc.invalidateQueries(['jobs']); setOpen(false); setTitle(''); setDesc('') },
  })

  return (
    <div className="max-w-4xl mx-auto p-6">
      <header className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Recruiter Dashboard</h1>
        <button onClick={() => setOpen(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 text-sm font-medium">
          + New Job
        </button>
      </header>

      {/* Job list */}
      <div className="grid gap-4">
        {jobs.map(j => (
          <div key={j.id} onClick={() => nav(`/recruiter/jobs/${j.id}`)}
            className="bg-white rounded-xl shadow p-5 cursor-pointer hover:shadow-md transition">
            <h2 className="font-semibold text-lg">{j.title}</h2>
            <p className="text-gray-400 text-sm mt-1">{new Date(j.created_at).toLocaleDateString()}</p>
          </div>
        ))}
        {jobs.length === 0 && (
          <p className="text-gray-400 text-center py-12">No jobs yet. Create your first role.</p>
        )}
      </div>

      {/* Create job modal */}
      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-lg">
            <h2 className="text-xl font-bold mb-4">Create Job</h2>
            <input placeholder="Job title" value={title} onChange={e => setTitle(e.target.value)}
              className="w-full border rounded-lg p-2.5 text-sm mb-3" />
            <textarea placeholder="Job description…" value={desc} onChange={e => setDesc(e.target.value)}
              className="w-full border rounded-lg p-2.5 text-sm h-40 mb-4 resize-none" />
            <div className="flex gap-3 justify-end">
              <button onClick={() => setOpen(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate()} disabled={!title || !desc}
                className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50">
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
