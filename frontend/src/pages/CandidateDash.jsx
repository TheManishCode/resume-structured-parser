import { useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadResume, myResumes, myScores } from '../api'

const SCORE_COLOR = s =>
  s >= 0.80 ? 'text-green-600' :
  s >= 0.60 ? 'text-amber-600' :
  s >= 0.40 ? 'text-orange-500' : 'text-red-500'

export default function CandidateDash() {
  const qc      = useQueryClient()
  const fileRef = useRef()

  const { data: resumes = [] } = useQuery({ queryKey: ['my-resumes'], queryFn: () => myResumes().then(r => r.data) })
  const { data: scores  = [] } = useQuery({ queryKey: ['my-scores'],  queryFn: () => myScores().then(r => r.data)  })

  const uploadMut = useMutation({
    mutationFn: (file) => uploadResume(file),
    onSuccess:  () => qc.invalidateQueries(['my-resumes']),
  })

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-8">Candidate Dashboard</h1>

      {/* Upload */}
      <section className="bg-white rounded-xl shadow p-6 mb-6">
        <h2 className="font-semibold text-lg mb-3">My Resume</h2>
        {resumes.length === 0 ? (
          <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center">
            <p className="text-gray-400 mb-4">No resume uploaded yet.</p>
            <button onClick={() => fileRef.current.click()}
              className="bg-indigo-600 text-white px-5 py-2 rounded-lg hover:bg-indigo-700 text-sm font-medium">
              Upload PDF / DOCX
            </button>
          </div>
        ) : (
          resumes.map(r => (
            <div key={r.id} className="flex items-center justify-between text-sm">
              <span className="text-gray-500 font-mono">{r.id.slice(0, 8)}…</span>
              <span className="text-gray-400">Expires {new Date(r.expires_at).toLocaleDateString()}</span>
              {r.used_ocr && <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">OCR</span>}
            </div>
          ))
        )}
        <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden"
          onChange={e => { if (e.target.files[0]) uploadMut.mutate(e.target.files[0]) }} />
      </section>

      {/* Scores */}
      <section className="bg-white rounded-xl shadow p-6">
        <h2 className="font-semibold text-lg mb-4">My Evaluations</h2>
        {scores.length === 0 && (
          <p className="text-gray-400 text-center py-8">Not evaluated against any role yet.</p>
        )}
        <div className="space-y-4">
          {scores.map(s => (
            <div key={s.id} className="border rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs text-gray-400">Job {s.job_id.slice(0, 8)}…</span>
                <span className={`text-2xl font-bold ${SCORE_COLOR(s.score)}`}>
                  {(s.score * 100).toFixed(1)}
                  <span className="text-sm font-normal text-gray-400"> / 100</span>
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-2">{s.justification}</p>
              {s.improvement_tip && (
                <div className="bg-indigo-50 text-indigo-700 text-sm rounded-lg px-4 py-2 mt-2">
                  💡 {s.improvement_tip}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
