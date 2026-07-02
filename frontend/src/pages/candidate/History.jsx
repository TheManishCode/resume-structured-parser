import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../../api'

function PageHeader({ title }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center justify-between bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
    </div>
  )
}

function ScorePill({ score }) {
  if (score == null) return <span className="text-zinc-400 text-xs">—</span>
  const cls = score >= 80 ? 'text-emerald-700 bg-emerald-50 ring-1 ring-emerald-100' :
              score >= 60 ? 'text-amber-700 bg-amber-50 ring-1 ring-amber-100'       :
                            'text-red-700 bg-red-50 ring-1 ring-red-100'
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded ${cls}`}>{score}</span>
}

export default function CandidateHistory() {
  const [page, setPage] = useState(0)
  const limit = 20

  const { data, isLoading } = useQuery({
    queryKey: ['candidate-history', page],
    queryFn:  () => api.getCandidateHistory(limit, page * limit),
    keepPreviousData: true,
  })

  const total = data?.total || 0
  const items = data?.items || []
  const pages = Math.ceil(total / limit)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Analysis history" />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        {isLoading ? (
          <div className="animate-pulse space-y-2">
            {[...Array(8)].map((_, i) => <div key={i} className="h-12 bg-zinc-200 rounded-lg" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <p className="text-zinc-600 font-medium mb-2">No analyses yet</p>
              <p className="text-zinc-400 text-sm mb-4">Your analysis history will appear here after each check.</p>
              <Link to="/candidate/analyze" className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                Analyze a resume
              </Link>
            </div>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto">
            <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500">Role</th>
                    <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500">Company</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">Overall</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">ATS</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">Keywords</th>
                    <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500">Missing</th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {items.map(a => (
                    <tr key={a.id} className="hover:bg-zinc-50 transition-colors">
                      <td className="px-5 py-3.5 text-zinc-800 font-medium max-w-[200px] truncate">{a.job_title || '—'}</td>
                      <td className="px-5 py-3.5 text-zinc-500 max-w-[150px] truncate">{a.company || '—'}</td>
                      <td className="px-5 py-3.5 text-right"><ScorePill score={a.overall_score} /></td>
                      <td className="px-5 py-3.5 text-right"><ScorePill score={a.ats_score} /></td>
                      <td className="px-5 py-3.5 text-right"><ScorePill score={a.keyword_match_score} /></td>
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap gap-1">
                          {(a.missing_keywords || []).slice(0, 3).map(kw => (
                            <span key={kw} className="text-[10px] bg-red-50 text-red-600 px-1.5 py-0.5 rounded">{kw}</span>
                          ))}
                          {(a.missing_keywords?.length || 0) > 3 && (
                            <span className="text-[10px] text-zinc-400">+{a.missing_keywords.length - 3}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right text-zinc-400 text-xs whitespace-nowrap">
                        {new Date(a.analyzed_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {pages > 1 && (
              <div className="flex items-center justify-between mt-4">
                <p className="text-xs text-zinc-500">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</p>
                <div className="flex gap-2">
                  <button disabled={page === 0} onClick={() => setPage(p => p - 1)}
                    className="text-xs px-3 py-1.5 rounded-md border border-zinc-200 disabled:opacity-40 hover:bg-zinc-100 transition-colors">
                    Previous
                  </button>
                  <button disabled={page >= pages - 1} onClick={() => setPage(p => p + 1)}
                    className="text-xs px-3 py-1.5 rounded-md border border-zinc-200 disabled:opacity-40 hover:bg-zinc-100 transition-colors">
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
