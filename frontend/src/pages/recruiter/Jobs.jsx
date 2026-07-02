import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../../api'

function PageHeader({ title, action }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center justify-between bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
      {action}
    </div>
  )
}

export default function RecruiterJobs() {
  const [search, setSearch] = useState('')

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['recruiter-jobs'],
    queryFn:  () => api.listJobs(),
  })

  const filtered = jobs.filter(j =>
    !search || j.title?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Jobs"
        action={
          <button className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-md transition-colors">
            + Post job
          </button>
        }
      />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        <div className="max-w-5xl mx-auto">
          {/* Search */}
          <div className="mb-4">
            <input
              type="search"
              placeholder="Search jobs…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full max-w-xs bg-white border border-zinc-200 rounded-lg px-3.5 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </div>

          {isLoading ? (
            <div className="animate-pulse space-y-2">
              {[...Array(5)].map((_, i) => <div key={i} className="h-14 bg-zinc-200 rounded-lg" />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center">
              <p className="text-zinc-600 font-medium mb-2">No jobs yet</p>
              <p className="text-zinc-400 text-sm mb-4">Post your first role to start scoring candidates.</p>
              <button className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                Post a job
              </button>
            </div>
          ) : (
            <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500">Title</th>
                    <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500">Status</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">Candidates</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">Created</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {filtered.map(j => (
                    <tr key={j.id} className="hover:bg-zinc-50 transition-colors">
                      <td className="px-5 py-3.5 font-medium text-zinc-900">
                        <Link to={`/recruiter/jobs/${j.id}`} className="hover:text-indigo-600 transition-colors">
                          {j.title}
                        </Link>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          j.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-zinc-100 text-zinc-500'
                        }`}>
                          {j.is_active ? 'Active' : 'Closed'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right text-zinc-500">{j.candidate_count ?? 0}</td>
                      <td className="px-5 py-3.5 text-right text-zinc-400 text-xs">
                        {j.created_at ? new Date(j.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-3 py-3.5 text-right">
                        <Link to={`/recruiter/jobs/${j.id}`} className="text-zinc-400 hover:text-indigo-600 transition-colors text-xs">
                          →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
