import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import api from '../../api'

function PageHeader({ title }) {
  return (
    <div className="h-14 px-6 border-b border-zinc-200 flex items-center bg-white shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
    </div>
  )
}

const DIST_COLORS = ['#ef4444', '#f59e0b', '#6366f1', '#10b981']

export default function RecruiterAnalytics() {
  const { data, isLoading } = useQuery({
    queryKey: ['recruiter-analytics'],
    queryFn:  () => api.getRecruiterAnalytics(),
  })

  const dist   = data?.score_distribution || []
  const skills = data?.top_skills_in_pool || []

  const distData = dist.map((d, i) => ({ ...d, fill: DIST_COLORS[i] || '#6366f1' }))

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Analytics" />
      <div className="flex-1 overflow-y-auto bg-zinc-50 p-6">
        {isLoading ? (
          <div className="animate-pulse space-y-4 max-w-5xl mx-auto">
            <div className="grid grid-cols-3 gap-4">
              {[0,1,2].map(i => <div key={i} className="h-20 bg-zinc-200 rounded-xl" />)}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="h-64 bg-zinc-200 rounded-xl" />
              <div className="h-64 bg-zinc-200 rounded-xl" />
            </div>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="Total scored" value={data?.total_scored ?? 0} />
              <StatCard label="Need review" value={data?.needs_review_count ?? 0} />
              <StatCard label="Top skills tracked" value={skills.length} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Score distribution */}
              <div className="bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">Score distribution</h3>
                {distData.some(d => d.count > 0) ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={distData} margin={{ left: -20, right: 4, top: 4, bottom: 0 }} barSize={36}>
                      <XAxis dataKey="range" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: '#18181b', border: 'none', borderRadius: 8, fontSize: 12 }} itemStyle={{ color: '#e4e4e7' }} labelStyle={{ color: '#a1a1aa' }} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {distData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-48 flex items-center justify-center">
                    <p className="text-sm text-zinc-400">Score candidates to see distribution.</p>
                  </div>
                )}
              </div>

              {/* Top skills in pool */}
              <div className="bg-white border border-zinc-200 rounded-xl p-5">
                <h3 className="text-sm font-medium text-zinc-800 mb-4">Top skills in candidate pool</h3>
                {skills.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={skills.slice(0, 10)} layout="vertical" margin={{ left: 40, right: 4, top: 0, bottom: 0 }} barSize={14}>
                      <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis dataKey="skill" type="category" tick={{ fontSize: 11, fill: '#52525b' }} width={60} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: '#18181b', border: 'none', borderRadius: 8, fontSize: 12 }} itemStyle={{ color: '#e4e4e7' }} />
                      <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-48 flex items-center justify-center">
                    <p className="text-sm text-zinc-400">Upload parsed resumes to see skill breakdown.</p>
                  </div>
                )}
              </div>
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
