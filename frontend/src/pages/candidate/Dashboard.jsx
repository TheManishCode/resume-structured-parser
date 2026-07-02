import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import api from '../../api'
import { useAuth } from '../../context/AuthContext'

function PageHeader({ title, action }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center justify-between shrink-0 bg-white">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
      {action}
    </div>
  )
}

function ScorePill({ score }) {
  if (score == null) return <span className="text-zinc-400">—</span>
  const cls = score >= 80 ? 'text-emerald-700 bg-emerald-50' :
              score >= 60 ? 'text-amber-700 bg-amber-50'    :
                            'text-red-700 bg-red-50'
  return <span className={`text-xs font-medium px-2 py-0.5 rounded ${cls}`}>{score}</span>
}

export default function CandidateDashboard() {
  const { auth } = useAuth()
  const { data, isLoading } = useQuery({
    queryKey: ['candidate-dashboard'],
    queryFn:  () => api.getCandidateDashboard(),
  })

  const completeness = data?.completeness
  const trend        = data?.recent_score_trend || []
  const missing      = data?.top_missing_skills || []
  const analyses     = data?.recent_analyses || []
  const firstName    = auth?.name?.split(' ')[0] || 'there'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Dashboard"
        action={
          <Link to="/candidate/analyze" className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-md transition-colors">
            + New analysis
          </Link>
        }
      />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        {isLoading ? (
          <Skeleton />
        ) : (
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Welcome */}
            <div>
              <h2 className="text-zinc-900 text-xl font-semibold">Good to see you, {firstName}.</h2>
              {!data?.candidate?.onboarding_done && (
                <p className="text-zinc-500 text-sm mt-1">
                  <Link to="/candidate/profile" className="text-indigo-600 hover:underline font-medium">Complete your profile</Link>
                  {' '}to get personalised recommendations.
                </p>
              )}
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="Total analyses" value={data?.total_analyses ?? 0} />
              <StatCard label="Resumes uploaded" value={data?.resume_count ?? 0} />
              <StatCard label="Profile complete" value={`${completeness?.score ?? 0}%`} />
            </div>

            {/* Profile completeness */}
            {completeness && completeness.score < 100 && (
              <div className="bg-white border border-zinc-200 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-zinc-800">Profile completeness</h3>
                  <span className="text-xs text-zinc-500">{completeness.score}%</span>
                </div>
                <div className="h-1.5 bg-zinc-100 rounded-full overflow-hidden mb-3">
                  <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${completeness.score}%` }} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {completeness.missing.map(m => (
                    <Link key={m} to="/candidate/profile"
                      className="text-xs text-zinc-500 bg-zinc-100 hover:bg-zinc-200 px-2.5 py-1 rounded-md transition-colors">
                      + {m}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-5 gap-4">
              {/* Score trend */}
              <div className="col-span-3 bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">ATS score trend</h3>
                {trend.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={trend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: '#18181b', border: 'none', borderRadius: 8, fontSize: 12 }} labelStyle={{ color: '#a1a1aa' }} itemStyle={{ color: '#e4e4e7' }} />
                      <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} fill="url(#scoreGrad)" dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState
                    msg="No scores yet"
                    sub="Run your first analysis to see how your ATS score changes over time."
                    cta={{ to: '/candidate/analyze', label: 'Analyze resume' }}
                  />
                )}
              </div>

              {/* Missing skills */}
              <div className="col-span-2 bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">Most missing skills</h3>
                {missing.length > 0 ? (
                  <div className="space-y-3">
                    {missing.map(({ skill, count }) => (
                      <div key={skill}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-zinc-700">{skill}</span>
                          <span className="text-zinc-400">{count}x</span>
                        </div>
                        <div className="h-1 bg-zinc-100 rounded-full overflow-hidden">
                          <div className="h-full bg-red-400 rounded-full" style={{ width: `${Math.min(count / (missing[0]?.count || 1) * 100, 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState msg="No data yet" sub="Missing keywords appear here after analyses." />
                )}
              </div>
            </div>

            {/* Recent analyses */}
            <div className="bg-white border border-zinc-200 rounded-xl">
              <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-100">
                <h3 className="text-sm font-medium text-zinc-800">Recent analyses</h3>
                <Link to="/candidate/history" className="text-xs text-indigo-600 hover:underline">View all</Link>
              </div>
              {analyses.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-100">
                      <th className="text-left px-5 py-2.5 text-xs font-medium text-zinc-500">Role</th>
                      <th className="text-left px-5 py-2.5 text-xs font-medium text-zinc-500">Company</th>
                      <th className="text-right px-5 py-2.5 text-xs font-medium text-zinc-500">Score</th>
                      <th className="text-right px-5 py-2.5 text-xs font-medium text-zinc-500">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyses.map(a => (
                      <tr key={a.id} className="border-b border-zinc-50 hover:bg-zinc-50 transition-colors">
                        <td className="px-5 py-3 text-zinc-800 font-medium">{a.job_title || '—'}</td>
                        <td className="px-5 py-3 text-zinc-500">{a.company || '—'}</td>
                        <td className="px-5 py-3 text-right"><ScorePill score={a.overall_score} /></td>
                        <td className="px-5 py-3 text-right text-zinc-400 text-xs">{new Date(a.analyzed_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="px-5 py-8 text-center">
                  <EmptyState
                    msg="No analyses yet"
                    sub="Upload your resume and check it against a job posting."
                    cta={{ to: '/candidate/analyze', label: 'Start analyzing' }}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl px-5 py-4">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className="text-2xl font-semibold text-zinc-900 tabular-nums">{value}</p>
    </div>
  )
}

function EmptyState({ msg, sub, cta }) {
  return (
    <div className="py-6 text-center">
      <p className="text-sm font-medium text-zinc-600">{msg}</p>
      {sub && <p className="text-xs text-zinc-400 mt-1 max-w-xs mx-auto">{sub}</p>}
      {cta && (
        <Link to={cta.to} className="inline-block mt-3 text-xs text-indigo-600 hover:underline font-medium">
          {cta.label} →
        </Link>
      )}
    </div>
  )
}

function Skeleton() {
  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="h-6 bg-zinc-200 rounded w-48" />
      <div className="grid grid-cols-3 gap-4">
        {[0,1,2].map(i => <div key={i} className="h-20 bg-zinc-200 rounded-xl" />)}
      </div>
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3 h-56 bg-zinc-200 rounded-xl" />
        <div className="col-span-2 h-56 bg-zinc-200 rounded-xl" />
      </div>
      <div className="h-48 bg-zinc-200 rounded-xl" />
    </div>
  )
}
