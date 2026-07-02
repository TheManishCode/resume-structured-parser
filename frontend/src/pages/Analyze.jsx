/**
 * Analyze.jsx — Public resume analysis page.
 *
 * Mode A: Job Match  — upload resume + URL (or paste JD) → scored match report
 * Mode B: ATS Check  — upload resume only → standalone ATS audit
 */
import { useRef, useState } from 'react'
import api from '../api'

// ── Utilities ─────────────────────────────────────────────────────────────────

function scoreColor(s) {
  if (s >= 80) return '#22c55e'
  if (s >= 60) return '#eab308'
  if (s >= 40) return '#f97316'
  return '#ef4444'
}

function scoreLabel(s) {
  if (s >= 80) return 'Excellent'
  if (s >= 60) return 'Good'
  if (s >= 40) return 'Fair'
  return 'Needs Work'
}

function scoreBg(s) {
  if (s >= 80) return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
  if (s >= 60) return 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200'
  if (s >= 40) return 'bg-orange-50 text-orange-700 ring-1 ring-orange-200'
  return 'bg-red-50 text-red-700 ring-1 ring-red-200'
}

// ── SVG Score Ring ────────────────────────────────────────────────────────────

function ScoreRing({ score, size = 140, label = null }) {
  const r    = (size - 20) / 2
  const circ = 2 * Math.PI * r
  const dash = circ * ((score ?? 0) / 100)
  const color = scoreColor(score ?? 0)
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f4f4f5" strokeWidth="10" />
        <circle
          cx={size/2} cy={size/2} r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />
        <text
          x="50%" y="50%"
          textAnchor="middle" dominantBaseline="middle"
          style={{ transform: 'rotate(90deg)', transformOrigin: '50% 50%', fill: color,
                   fontSize: size < 100 ? 18 : 26, fontWeight: 700, fontFamily: 'inherit' }}
        >
          {score ?? '—'}
        </text>
      </svg>
      {label && <p className="text-xs text-zinc-500 font-medium">{label}</p>}
    </div>
  )
}

// ── Score Bar (sub-score) ─────────────────────────────────────────────────────

function ScoreBar({ label, score, help = '' }) {
  const color = score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-yellow-400' : score >= 40 ? 'bg-orange-400' : 'bg-red-400'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-zinc-700 font-medium">{label}</span>
        <span className="font-semibold text-zinc-800">{score}/100</span>
      </div>
      <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      {help && <p className="text-[11px] text-zinc-400 mt-1">{help}</p>}
    </div>
  )
}

// ── Issue badge ───────────────────────────────────────────────────────────────

function IssueBadge({ severity }) {
  const cls = severity === 'high'   ? 'bg-red-100 text-red-700'    :
              severity === 'medium' ? 'bg-amber-100 text-amber-700' :
                                      'bg-zinc-100 text-zinc-600'
  return (
    <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${cls}`}>
      {severity}
    </span>
  )
}

// ── Chip ─────────────────────────────────────────────────────────────────────

function Chip({ text, matched = true }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full ${
      matched
        ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100'
        : 'bg-red-50 text-red-600 ring-1 ring-red-100'
    }`}>
      {matched ? '✓' : '✗'} {text}
    </span>
  )
}

// ── Section check table ───────────────────────────────────────────────────────

function SectionChecklist({ sections }) {
  const items = Object.entries(sections)
  return (
    <div className="grid grid-cols-2 gap-2">
      {items.map(([key, present]) => (
        <div key={key} className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
          present ? 'bg-emerald-50 text-emerald-800' : 'bg-zinc-50 text-zinc-500'
        }`}>
          <span className={`text-base ${present ? 'text-emerald-500' : 'text-zinc-300'}`}>
            {present ? '✓' : '○'}
          </span>
          <span className="capitalize">{key.replace(/_/g, ' ')}</span>
        </div>
      ))}
    </div>
  )
}

// ── Loading screen ────────────────────────────────────────────────────────────

const MESSAGES_MATCH = [
  'Parsing your resume…', 'Fetching job description…', 'Extracting keywords…',
  'Matching skills…', 'Running AI analysis…', 'Generating insights…',
]
const MESSAGES_ATS = [
  'Parsing your resume…', 'Checking ATS compatibility…', 'Analyzing format…',
  'Evaluating content quality…', 'Extracting skills…', 'Generating report…',
]

function LoadingScreen({ mode }) {
  const msgs = mode === 'ats' ? MESSAGES_ATS : MESSAGES_MATCH
  const [idx, setIdx] = useState(0)
  useState(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % msgs.length), 1800)
    return () => clearInterval(t)
  })
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6">
      <div className="w-12 h-12 rounded-full border-4 border-indigo-100 border-t-indigo-600 animate-spin" />
      <p className="text-sm text-zinc-600 font-medium min-h-[20px]">{msgs[idx]}</p>
      <div className="flex gap-1.5">
        {msgs.map((_, i) => (
          <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors ${i === idx ? 'bg-indigo-600' : 'bg-zinc-200'}`} />
        ))}
      </div>
    </div>
  )
}

// ── Job Match Results ─────────────────────────────────────────────────────────

function MatchResults({ data, onReset }) {
  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
          <ScoreRing score={data.overall_score} size={140} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h2 className="text-lg font-semibold text-zinc-900">
                {data.job_title || 'Job Match Analysis'}
              </h2>
              {data.company && <span className="text-zinc-400 text-sm">@ {data.company}</span>}
            </div>
            <p className={`text-xs font-semibold px-2.5 py-1 rounded-full inline-block mb-3 ${scoreBg(data.overall_score)}`}>
              {scoreLabel(data.overall_score)} match
              {data.seniority_match && data.seniority_match !== 'match' && (
                <span className="ml-2 opacity-75">· {data.seniority_match}</span>
              )}
            </p>
            {data.summary && (
              <p className="text-sm text-zinc-600 leading-relaxed">{data.summary}</p>
            )}
          </div>
        </div>
      </div>

      {/* Sub-scores */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-semibold text-zinc-800">Score breakdown</h3>
        <ScoreBar label="ATS keyword pass-through" score={data.ats_score} help="Likelihood this resume makes it through automated keyword filters" />
        <ScoreBar label="Keyword match"            score={data.keyword_match_score} help="Job description terms found in your resume" />
        <ScoreBar label="Skills match"             score={data.skills_match_score} help="Required skills vs. skills on your resume" />
        <ScoreBar label="Experience relevance"     score={data.experience_score} />
        <ScoreBar label="Format & structure"       score={data.format_score} />
      </div>

      {/* Keywords */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Matched keywords ({data.matched_keywords?.length || 0})
          </h3>
          <div className="flex flex-wrap gap-2">
            {(data.matched_keywords || []).map(kw => <Chip key={kw} text={kw} matched />)}
            {!data.matched_keywords?.length && <p className="text-xs text-zinc-400">None found</p>}
          </div>
        </div>
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Missing keywords ({data.missing_keywords?.length || 0})
          </h3>
          <div className="flex flex-wrap gap-2">
            {(data.missing_keywords || []).map(kw => <Chip key={kw} text={kw} matched={false} />)}
            {!data.missing_keywords?.length && <p className="text-xs text-zinc-400">Great — no critical gaps</p>}
          </div>
        </div>
      </div>

      {/* Strengths / Improvements / Red flags */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {data.strengths?.length > 0 && (
          <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-3">Strengths</h3>
            <ul className="space-y-2">
              {data.strengths.map((s, i) => (
                <li key={i} className="text-sm text-emerald-800 flex gap-2">
                  <span className="shrink-0 mt-0.5 text-emerald-400">✓</span>{s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.improvements?.length > 0 && (
          <div className="bg-amber-50 border border-amber-100 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-3">Improvements</h3>
            <ol className="space-y-2.5 list-none">
              {data.improvements.map((s, i) => (
                <li key={i} className="text-sm text-amber-800 flex gap-2">
                  <span className="shrink-0 font-bold text-amber-400 w-4">{i + 1}.</span>{s}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {data.red_flags?.length > 0 && (
        <div className="bg-red-50 border border-red-100 rounded-2xl p-5">
          <h3 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3">Red flags</h3>
          <ul className="space-y-2">
            {data.red_flags.map((s, i) => (
              <li key={i} className="text-sm text-red-800 flex gap-2">
                <span className="shrink-0 text-red-400">!</span>{s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Resume health stats */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Resume health</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Stat label="Word count" value={data.resume_word_count} note="400–900 ideal" />
          <Stat label="Quantification" value={`${Math.round((data.quant_ratio || 0) * 100)}%`} note="40%+ recommended" />
          <Stat label="Sections found" value={data.sections_found?.length} note="aim for 5+" />
          <Stat label="Contact info" value={data.has_contact_info ? 'Complete' : 'Incomplete'} />
        </div>
      </div>

      <button onClick={onReset}
        className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 text-white text-sm font-medium rounded-xl transition-colors">
        Check another resume
      </button>
    </div>
  )
}

// ── ATS-only Results ──────────────────────────────────────────────────────────

function AtsResults({ data, onReset }) {
  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header — 4 score rings */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-6">
        <div className="flex items-start justify-between flex-wrap gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">ATS Audit Report</h2>
            {data.career_level && data.career_level !== 'unknown' && (
              <span className="text-xs text-zinc-500 capitalize">Detected level: {data.career_level}</span>
            )}
          </div>
          {data.likely_roles?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.likely_roles.slice(0, 3).map(r => (
                <span key={r} className="text-xs bg-indigo-50 text-indigo-700 ring-1 ring-indigo-100 px-2.5 py-1 rounded-full">{r}</span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-6 justify-around pt-2">
          <ScoreRing score={data.overall_ats_score} size={120} label="Overall ATS" />
          <ScoreRing score={data.parsability_score} size={100} label="Parsability" />
          <ScoreRing score={data.contact_score}      size={100} label="Contact" />
          <ScoreRing score={data.content_score}      size={100} label="Content" />
          <ScoreRing score={data.format_score}       size={100} label="Format" />
        </div>

        {data.summary && (
          <p className="mt-5 text-sm text-zinc-600 leading-relaxed border-t border-zinc-100 pt-4">
            {data.summary}
          </p>
        )}
      </div>

      {/* Issues */}
      {data.issues?.length > 0 && (
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-zinc-800 mb-3">
            Detected issues <span className="text-zinc-400 font-normal">({data.issues.length})</span>
          </h3>
          <div className="space-y-3">
            {data.issues.map((issue, i) => (
              <div key={i} className={`flex gap-3 p-3 rounded-lg text-sm ${
                issue.severity === 'high'   ? 'bg-red-50'    :
                issue.severity === 'medium' ? 'bg-amber-50'  : 'bg-zinc-50'
              }`}>
                <IssueBadge severity={issue.severity} />
                <p className={
                  issue.severity === 'high'   ? 'text-red-800'   :
                  issue.severity === 'medium' ? 'text-amber-800' : 'text-zinc-700'
                }>{issue.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sections check */}
      {data.key_sections && (
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-zinc-800 mb-3">Section checklist</h3>
          <SectionChecklist sections={data.key_sections} />
        </div>
      )}

      {/* Skills & keywords */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {data.skills_extracted?.length > 0 && (
          <div className="bg-white border border-zinc-200 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              Skills detected ({data.skills_extracted.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {data.skills_extracted.map(s => (
                <span key={s} className="text-xs bg-indigo-50 text-indigo-700 ring-1 ring-indigo-100 px-2.5 py-1 rounded-full">{s}</span>
              ))}
            </div>
          </div>
        )}
        {data.suggested_keywords?.length > 0 && (
          <div className="bg-white border border-zinc-200 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              Suggested additions
            </h3>
            <div className="flex flex-wrap gap-2">
              {data.suggested_keywords.map(s => (
                <span key={s} className="text-xs bg-zinc-100 text-zinc-600 px-2.5 py-1 rounded-full">+ {s}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Strengths / Improvements */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {data.strengths?.length > 0 && (
          <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-3">Strengths</h3>
            <ul className="space-y-2">
              {data.strengths.map((s, i) => (
                <li key={i} className="text-sm text-emerald-800 flex gap-2">
                  <span className="shrink-0 text-emerald-400">✓</span>{s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.improvements?.length > 0 && (
          <div className="bg-amber-50 border border-amber-100 rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-3">What to fix</h3>
            <ol className="space-y-2.5">
              {data.improvements.map((s, i) => (
                <li key={i} className="text-sm text-amber-800 flex gap-2">
                  <span className="shrink-0 font-bold text-amber-400 w-4">{i + 1}.</span>{s}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* Content stats */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Content metrics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Stat label="Word count"     value={data.word_count}    note="400–900 ideal" />
          <Stat label="Bullet points"  value={data.bullet_count}  />
          <Stat label="Quantified"     value={`${Math.round((data.quant_ratio || 0) * 100)}%`} note="40%+ aim" />
          <Stat label="Action verbs"   value={data.action_verbs}  note="8+ is strong" />
        </div>
      </div>

      <button onClick={onReset}
        className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 text-white text-sm font-medium rounded-xl transition-colors">
        Check another resume
      </button>
    </div>
  )
}

function Stat({ label, value, note }) {
  return (
    <div className="text-center">
      <p className="text-xl font-semibold text-zinc-900 tabular-nums">{value ?? '—'}</p>
      <p className="text-[11px] text-zinc-500 mt-0.5">{label}</p>
      {note && <p className="text-[10px] text-zinc-400">{note}</p>}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

const PLATFORM_LOGOS = {
  linkedin:    { label: 'LinkedIn',    color: '#0A66C2' },
  indeed:      { label: 'Indeed',      color: '#003A9B' },
  glassdoor:   { label: 'Glassdoor',   color: '#0CAA41' },
  greenhouse:  { label: 'Greenhouse',  color: '#3CAA5A' },
  lever:       { label: 'Lever',       color: '#1E5FA6' },
  workday:     { label: 'Workday',     color: '#E26C00' },
  wellfound:   { label: 'Wellfound',   color: '#666' },
}

export default function Analyze({ embedded = false }) {
  const fileRef = useRef()

  // Mode: 'match' | 'ats'
  const [mode,     setMode]     = useState('match')
  const [file,     setFile]     = useState(null)
  const [jobUrl,   setJobUrl]   = useState('')
  const [jobText,  setJobText]  = useState('')
  const [showPaste, setShowPaste] = useState(false)
  const [dragging, setDragging] = useState(false)

  // State machine: 'form' | 'loading' | 'result' | 'error'
  const [state,    setState]    = useState('form')
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState(null)

  function handleFile(f) {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!['pdf', 'doc', 'docx'].includes(ext)) {
      setError('Please upload a PDF or DOCX file.')
      return
    }
    setFile(f)
    setError(null)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) { setError('Upload your resume first.'); return }

    if (mode === 'match') {
      const hasUrl  = jobUrl.trim().length > 0
      const hasText = jobText.trim().length > 50
      if (!hasUrl && !hasText) {
        setError('Provide a job URL or paste the job description.')
        return
      }
    }

    setState('loading')
    setError(null)

    try {
      let data
      if (mode === 'ats') {
        data = await api.checkAts(file)
      } else {
        data = await api.analyzeResume(file, jobUrl.trim(), jobText.trim())
      }
      setResult(data)
      setState('result')
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Analysis failed'
      if (detail?.scrape_failed || (typeof detail === 'string' && detail.includes('paste'))) {
        setShowPaste(true)
        setError(detail?.message || detail)
        setState('form')
      } else {
        setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
        setState('form')
      }
    }
  }

  function reset() {
    setState('form')
    setResult(null)
    setError(null)
    setFile(null)
    setJobUrl('')
    setJobText('')
    setShowPaste(false)
  }

  const wrapperCls = embedded
    ? 'flex flex-col h-full overflow-hidden'
    : 'min-h-screen bg-zinc-50'

  return (
    <div className={wrapperCls}>
      {/* Header — only shown standalone */}
      {!embedded && (
        <header className="bg-white border-b border-zinc-200 px-6 h-14 flex items-center justify-between">
          <span className="font-semibold text-zinc-900 tracking-tight text-sm">ResumeIQ</span>
          <div className="flex items-center gap-3">
            <a href="/login" className="text-sm text-zinc-500 hover:text-zinc-800 transition-colors">Sign in</a>
            <a href="/signup/candidate" className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3.5 py-2 rounded-lg transition-colors">
              Get started free
            </a>
          </div>
        </header>
      )}

      {/* Scrollable content */}
      <div className={embedded ? 'flex-1 overflow-y-auto bg-zinc-50' : ''}>
        <div className="max-w-3xl mx-auto px-4 py-8">

          {/* Subhed — only standalone */}
          {!embedded && state === 'form' && (
            <div className="text-center mb-8">
              <h1 className="text-2xl font-semibold text-zinc-900 mb-2">Resume analysis, no sign-up needed</h1>
              <p className="text-zinc-500 text-sm">Check your resume against a job posting, or audit it for ATS compatibility.</p>
            </div>
          )}

          {state === 'loading' && <LoadingScreen mode={mode} />}

          {state === 'result' && result && (
            mode === 'ats'
              ? <AtsResults data={result} onReset={reset} />
              : <MatchResults data={result} onReset={reset} />
          )}

          {state === 'form' && (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Mode toggle */}
              <div className="flex bg-white border border-zinc-200 rounded-xl p-1">
                <ModeTab active={mode === 'match'} onClick={() => setMode('match')}>
                  <span className="mr-1.5">↔</span> Job Match
                  <span className="ml-2 text-[10px] text-zinc-400 font-normal">compare resume to a JD</span>
                </ModeTab>
                <ModeTab active={mode === 'ats'} onClick={() => setMode('ats')}>
                  <span className="mr-1.5">✓</span> ATS Check
                  <span className="ml-2 text-[10px] text-zinc-400 font-normal">audit resume itself</span>
                </ModeTab>
              </div>

              {/* File drop zone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  dragging
                    ? 'border-indigo-400 bg-indigo-50'
                    : file
                      ? 'border-emerald-300 bg-emerald-50'
                      : 'border-zinc-200 bg-white hover:border-zinc-400 hover:bg-zinc-50'
                }`}
              >
                <input
                  ref={fileRef} type="file" accept=".pdf,.doc,.docx"
                  className="hidden" onChange={e => handleFile(e.target.files[0])}
                />
                {file ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 text-lg">✓</div>
                    <p className="text-sm font-medium text-emerald-800">{file.name}</p>
                    <p className="text-xs text-emerald-600">{(file.size / 1024).toFixed(0)} KB — click to replace</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-500 text-lg">↑</div>
                    <p className="text-sm font-medium text-zinc-700">Drop your resume here or click to browse</p>
                    <p className="text-xs text-zinc-400">PDF or DOCX · max 10 MB</p>
                  </div>
                )}
              </div>

              {/* Job URL / paste (only for match mode) */}
              {mode === 'match' && (
                <div className="bg-white border border-zinc-200 rounded-xl p-5 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-2">
                      Job posting URL
                    </label>
                    <input
                      type="url"
                      value={jobUrl}
                      onChange={e => setJobUrl(e.target.value)}
                      placeholder="https://linkedin.com/jobs/view/…  or  https://boards.greenhouse.io/…"
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3.5 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition"
                    />
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {Object.entries(PLATFORM_LOGOS).map(([key, { label, color }]) => (
                        <span key={key} className="text-[10px] font-medium px-2 py-0.5 rounded bg-zinc-100 text-zinc-500">
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Paste toggle */}
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowPaste(p => !p)}
                      className="text-xs text-indigo-600 hover:text-indigo-700 font-medium transition-colors"
                    >
                      {showPaste ? '− Hide' : '+ Paste job description manually'} (use if URL fails)
                    </button>
                    {showPaste && (
                      <textarea
                        value={jobText}
                        onChange={e => setJobText(e.target.value)}
                        rows={8}
                        placeholder="Paste the full job description text here…"
                        className="mt-2 w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3.5 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition resize-y"
                      />
                    )}
                  </div>
                </div>
              )}

              {/* ATS mode note */}
              {mode === 'ats' && (
                <div className="bg-indigo-50 border border-indigo-100 rounded-xl px-5 py-4 text-sm text-indigo-800">
                  <strong>ATS Check mode</strong> — no job description needed. We audit your resume's format, contact info, content quality, and keyword density. Get a score and specific fixes.
                </div>
              )}

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-800">
                  {error}
                  {showPaste && !jobText && (
                    <p className="mt-1 text-red-600 font-medium">↑ Paste the job description above to continue.</p>
                  )}
                </div>
              )}

              <button
                type="submit"
                className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm shadow-indigo-200"
              >
                {mode === 'ats' ? 'Run ATS Audit' : 'Analyze Resume'}
              </button>

              {!embedded && (
                <p className="text-center text-xs text-zinc-400">
                  Your resume is analyzed privately and never stored without your account.{' '}
                  <a href="/signup/candidate" className="text-indigo-500 hover:underline">Create an account</a> to save history.
                </p>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

function ModeTab({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
        active
          ? 'bg-zinc-900 text-white shadow-sm'
          : 'text-zinc-500 hover:text-zinc-700'
      }`}
    >
      {children}
    </button>
  )
}
