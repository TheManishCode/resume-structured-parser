import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getJob, rankJob, scoreResume } from '../api'

const STATUS_BADGE = {
  confirmed:   'bg-green-100 text-green-700',
  provisional: 'bg-amber-100 text-amber-700',
  re_scored:   'bg-blue-100 text-blue-700',
}

const MODEL_LABEL = {
  local:    '⚡ Local',
  claude:   '☁ Claude',
  groq:     '🔁 Groq',
  fallback: '⚠ Fallback',
}

export default function JobDetail() {
  const { jobId } = useParams()
  const qc = useQueryClient()

  const { data: job }      = useQuery({ queryKey: ['job', jobId],  queryFn: () => getJob(jobId).then(r => r.data) })
  const { data: ranked = [] } = useQuery({ queryKey: ['rank', jobId], queryFn: () => rankJob(jobId, 50).then(r => r.data) })

  const scoreMut = useMutation({
    mutationFn: ({ resumeId, cloud }) => scoreResume(jobId, resumeId, cloud),
    onSuccess:  () => qc.invalidateQueries(['rank', jobId]),
  })

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">{job?.title ?? '…'}</h1>
      <p className="text-gray-500 text-sm mb-8 line-clamp-3">{job?.description}</p>

      <h2 className="font-semibold text-lg mb-4">Ranked Shortlist</h2>

      {ranked.length === 0 && (
        <p className="text-gray-400 text-center py-12">No candidates scored yet.</p>
      )}

      <div className="space-y-3">
        {ranked.map((row, i) => (
          <div key={row.resume_id}
            className={`bg-white rounded-xl shadow p-5 ${row.needs_review ? 'border-l-4 border-amber-400' : ''}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xl font-bold text-indigo-600">#{i + 1}</span>
                  <span className="font-mono text-sm text-gray-500">{row.resume_id.slice(0, 8)}…</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[row.status] ?? ''}`}>
                    {row.status}
                  </span>
                  <span className="text-xs text-gray-400">{MODEL_LABEL[row.scored_by] ?? row.scored_by}</span>
                  {row.needs_review && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                      ⚠ Review — Δ{row.disagreement_delta?.toFixed(2)}
                    </span>
                  )}
                  {row.previous_score != null && (
                    <span className="text-xs text-gray-400">
                      (prev {row.previous_score.toFixed(3)})
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-600 mt-1">{row.justification}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-2xl font-bold text-indigo-700">{(row.score * 100).toFixed(1)}</div>
                <div className="text-xs text-gray-400">/ 100</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
