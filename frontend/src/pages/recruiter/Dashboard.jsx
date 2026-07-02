import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  FunnelChart, Funnel, LabelList, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Cell,
} from 'recharts'
import api from '../../api'
import { useAuth } from '../../context/AuthContext'

function PageHeader({ title, action }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center justify-between bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
      {action}
    </div>
  )
}

const FUNNEL_COLORS = ['#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff']

export default function RecruiterDashboard() {
  const { auth } = useAuth()
  const { data, isLoading } = useQuery({
    queryKey: ['recruiter-dashboard'],
    queryFn:  () => api.getRecruiterDashboard(),
  })

  const funnel = data?.hiring_funnel
  const perf   = data?.job_performance || []
  const firstName = auth?.name?.split(' ')[0] || 'there'

  const funnelData = funnel ? [
    { name: 'Uploaded',    value: funnel.uploaded,    fill: FUNNEL_COLORS[0] },
    { name: 'Parsed',      value: funnel.parsed,      fill: FUNNEL_COLORS[1] },
    { name: 'Scored',      value: funnel.scored,      fill: FUNNEL_COLORS[2] },
    { name: 'Matched 50%+', value: funnel.matched,   fill: FUNNEL_COLORS[3] },
    { name: 'Shortlisted', value: funnel.shortlisted, fill: FUNNEL_COLORS[4] },
  ] : []

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Dashboard"
        action={
          <Link to="/recruiter/jobs" className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-md transition-colors">
            + Post job
          </Link>
        }
      />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        {isLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-zinc-200 rounded w-48" />
            <div className="grid grid-cols-4 gap-4">{[0,1,2,3].map(i => <div key={i} className="h-20 bg-zinc-200 rounded-xl"/>)}</div>
            <div className="grid grid-cols-5 gap-4">
              <div className="col-span-2 h-60 bg-zinc-200 rounded-xl" />
              <div className="col-span-3 h-60 bg-zinc-200 rounded-xl" />
            </div>
          </div>
        ) : (
          <div className="max-w-6xl mx-auto space-y-6">
            <div>
              <h2 className="text-zinc-900 text-xl font-semibold">Welcome back, {firstName}.</h2>
              {data?.recruiter && !data.recruiter.onboarding_done && (
                <p className="text-zinc-500 text-sm mt-1">
                  <Link to="/recruiter/profile" className="text-indigo-600 hover:underline font-medium">Complete your company profile</Link>
                  {' '}to get better results.
                </p>
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-4">
              <StatCard label="Active jobs" value={data?.active_jobs ?? 0} />
              <StatCard label="Resumes scored" value={data?.total_scored ?? 0} />
              <StatCard label="Matched (50%+)" value={data?.matched ?? 0} />
              <StatCard label="Shortlisted (70%+)" value={data?.shortlisted ?? 0} color="indigo" />
            </div>

            <div className="grid grid-cols-5 gap-4">
              {/* Hiring funnel */}
              <div className="col-span-2 bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">Hiring funnel</h3>
                {funnelData.some(d => d.value > 0) ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <FunnelChart>
                      <Tooltip
                        contentStyle={{ background: '#18181b', border: 'none', borderRadius: 8, fontSize: 12 }}
                        itemStyle={{ color: '#e4e4e7' }}
                      />
                      <Funnel dataKey="value" data={funnelData} isAnimationActive>
                        {funnelData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                        <LabelList dataKey="name" position="right" style={{ fill: '#71717a', fontSize: 11 }} />
                      </Funnel>
                    </FunnelChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-48 flex items-center justify-center text-center">
                    <div>
                      <p className="text-sm text-zinc-500 mb-2">No data yet</p>
                      <p className="text-xs text-zinc-400">Post a job and upload resumes to see funnel data.</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Job performance */}
              <div className="col-span-3 bg-white border border-zinc-200 rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-zinc-800">Job performance</h3>
                  <Link to="/recruiter/jobs" className="text-xs text-indigo-600 hover:underline">View all jobs</Link>
                </div>
                {perf.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={perf} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barSize={24}>
                      <XAxis dataKey="title" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false}
                        tickFormatter={v => v.length > 12 ? v.slice(0, 12) + '…' : v} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ background: '#18181b', border: 'none', borderRadius: 8, fontSize: 12 }}
                        itemStyle={{ color: '#e4e4e7' }} labelStyle={{ color: '#a1a1aa' }}
                      />
                      <Bar dataKey="avg_score" name="Avg score" radius={[4, 4, 0, 0]} fill="#6366f1" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-48 flex items-center justify-center">
                    <div className="text-center">
                      <p className="text-sm text-zinc-500">No active jobs with scores</p>
                      <Link to="/recruiter/jobs" className="text-xs text-indigo-600 hover:underline mt-2 block">Post your first job →</Link>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Recent activity */}
            {data?.recent_activity?.length > 0 && (
              <div className="bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">Recent activity</h3>
                <div className="space-y-2">
                  {data.recent_activity.map((e, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-zinc-50 last:border-0">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-sm text-zinc-700 capitalize">{e.event?.replace(/_/g, ' ')} · {e.entity}</span>
                      </div>
                      <span className="text-xs text-zinc-400">{new Date(e.occurred_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl px-5 py-4">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${color === 'indigo' ? 'text-indigo-600' : 'text-zinc-900'}`}>{value}</p>
    </div>
  )
}
