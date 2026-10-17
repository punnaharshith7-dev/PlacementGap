import { useEffect, useMemo, useState } from 'react'
import ApprovalGate from './ApprovalGate'
import AuthPage, { type PlacementUser } from './AuthPage'
import CareerStudio from './CareerStudio'
import { careerTabs, type CareerTab, type SavedRole } from './careerTypes'
import EvalDashboard from './EvalDashboard'
import EvidenceLedger from './EvidenceLedger'
import Landing from './Landing'
import Overview from './Overview'
import RunDiff from './RunDiff'
import RunGraph from './RunGraph'
import TracePanel from './TracePanel'
import type { RunEvent, RunState, TraceRow } from './types'

const api = (path: string) => `${import.meta.env.VITE_API_URL ?? ''}${path}`
const nav = ['Overview', 'Analyze', 'Roles', 'Compare', 'Roadmap', 'Skill Lab', 'Portfolio', 'Resources', 'Market', 'Application Kit', 'Applications', 'Trace', 'Evals'] as const
type Tab = typeof nav[number]
type Page = 'landing' | 'auth' | 'dashboard' | 'callback'

function pageFromLocation(): Page {
  const path = window.location.pathname
  if (new URLSearchParams(window.location.search).has('auth_error')) return 'auth'
  if (path === '/dashboard') return 'dashboard'
  if (path === '/signin' || path === '/signup') return 'auth'
  if (path === '/auth/callback') return 'callback'
  return 'landing'
}

function BrandMark() {
  return <img className="brand-emblem" src="/placementgap-growth-mark.png" alt="" />
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromLocation)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>(window.location.pathname === '/signup' ? 'signup' : 'signin')
  const [tab, setTab] = useState<Tab>('Overview')
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null)
  const [user, setUser] = useState<PlacementUser | null>(null)
  const [checkingSession, setCheckingSession] = useState(pageFromLocation() === 'dashboard' || pageFromLocation() === 'callback')
  const [studentId, setStudentId] = useState('')
  const [profile, setProfile] = useState('')
  const [profileFile, setProfileFile] = useState<{ filename: string; base64: string } | null>(null)
  const [jd, setJd] = useState('')
  const [jdUrl, setJdUrl] = useState('')
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [weeks, setWeeks] = useState(8)
  const [hours, setHours] = useState(8)
  const [run, setRun] = useState<RunState | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [traces, setTraces] = useState<TraceRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [stream, setStream] = useState<EventSource | null>(null)

  useEffect(() => () => stream?.close(), [stream])
  const cost = useMemo(() => traces.reduce((sum, row) => sum + row.cost_usd, 0), [traces])

  const navigate = (destination: Page, pathname: string, replace = false) => {
    if (replace) window.history.replaceState({}, '', pathname)
    else window.history.pushState({}, '', pathname)
    setPage(destination)
  }
  const goHome = () => navigate('landing', '/')
  const goSignIn = (mode: 'signin' | 'signup' = 'signin') => {
    setAuthMode(mode); navigate('auth', mode === 'signup' ? '/signup' : '/signin')
  }
  const openDashboard = (nextUser: PlacementUser) => {
    setUser(nextUser); setStudentId(nextUser.id); setTab('Overview'); navigate('dashboard', '/dashboard', true)
  }
  const refresh = async (runId: string) => {
    const [runResponse, traceResponse] = await Promise.all([
      fetch(api(`/runs/${runId}`), { credentials: 'include' }), fetch(api(`/runs/${runId}/trace`), { credentials: 'include' }),
    ])
    if (runResponse.ok) setRun(await runResponse.json())
    if (traceResponse.ok) { const payload = await traceResponse.json(); setTraces(payload.traces ?? []); setEvents(payload.events ?? []) }
  }
  const follow = (runId: string) => {
    stream?.close()
    const source = new EventSource(api(`/runs/${runId}/stream`), { withCredentials: true })
    setStream(source)
    const types = ['run_start', 'node_start', 'node_end', 'tool_call', 'token_delta', 'interrupt', 'approval_resume', 'run_error', 'run_end']
    for (const type of types) source.addEventListener(type, event => {
      const message = event as MessageEvent
      let data: Record<string, unknown> = {}
      try { data = JSON.parse(message.data) } catch { /* show the event even when its payload is not JSON */ }
      setEvents(current => [...current, { id: Number(message.lastEventId || current.length + 1), type, data, created_at: new Date().toISOString() }])
      if (type === 'interrupt') setTab('Analyze')
      if (type === 'run_end' || type === 'run_error') { source.close(); setStream(null) }
      void refresh(runId)
    })
    source.onerror = () => { void refresh(runId) }
  }
  const start = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError(''); setEvents([]); setTraces([])
    try {
      const payload: Record<string, unknown> = {
        student_id: studentId || user?.id,
        profile_text: profileFile ? '' : profile,
        profile_filename: profileFile?.filename,
        profile_file_base64: profileFile?.base64,
        jd_text: jd,
        jd_url: jdUrl || undefined,
        role,
        company,
        weeks,
        hours_per_week: hours,
      }
      const response = await fetch(api('/runs'), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify(payload),
      })
      const value = await response.json()
      if (!response.ok) throw new Error(value.detail ?? 'Unable to start analysis')
      if (user) localStorage.setItem(`placementgap:lastRun:${user.id}`, value.run_id)
      setTab('Analyze'); await refresh(value.run_id); follow(value.run_id)
    } catch (exception) { setError(exception instanceof Error ? exception.message : 'Request failed') } finally { setLoading(false) }
  }
  const upload = async (file?: File) => {
    if (!file) return
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1] ?? ''); reader.onerror = () => reject(reader.error); reader.readAsDataURL(file)
    })
    setProfileFile({ filename: file.name, base64 })
  }
  const onApproval = () => { if (run) { setRun({ ...run, status: 'resuming' }); follow(run.run_id) } }
  const analyzeSavedRole = (savedRole: SavedRole) => {
    setSelectedTargetId(savedRole.id)
    setRole(savedRole.title)
    setCompany(savedRole.company)
    setJd(savedRole.description)
    setJdUrl(savedRole.url || '')
    setTab('Analyze')
  }
  const signOut = async () => {
    await fetch(api('/auth/logout'), { method: 'POST', credentials: 'include' }).catch(() => undefined)
    stream?.close(); setStream(null); setUser(null); setRun(null); setEvents([]); setTraces([]); setStudentId(''); goHome()
  }

  useEffect(() => {
    const onPopState = () => { const destination = pageFromLocation(); setPage(destination); if (window.location.pathname === '/signup') setAuthMode('signup'); else if (window.location.pathname === '/signin') setAuthMode('signin') }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    if (page !== 'dashboard' && page !== 'callback') { setCheckingSession(false); return }
    setCheckingSession(true)
    void fetch(api('/auth/me'), { credentials: 'include' }).then(async response => {
      if (!response.ok) throw new Error('Sign-in required')
      const value = await response.json() as { user: PlacementUser }
      setUser(value.user); setStudentId(value.user.id)
      if (page === 'callback') navigate('dashboard', '/dashboard', true)
      const lastRun = localStorage.getItem(`placementgap:lastRun:${value.user.id}`)
      if (lastRun) void refresh(lastRun).catch(() => localStorage.removeItem(`placementgap:lastRun:${value.user.id}`))
    }).catch(() => {
      if (page === 'dashboard' || page === 'callback') { setAuthMode('signin'); navigate('auth', '/signin', true) }
    }).finally(() => setCheckingSession(false))
  }, [page])

  if (checkingSession) return <div className="auth-loading"><BrandMark /><span>Opening your workspace…</span></div>
  if (page === 'landing') return <Landing onSignIn={() => goSignIn('signin')} onGetStarted={() => goSignIn('signup')} />
  if (page === 'auth' || page === 'callback') return <AuthPage initialMode={authMode} onAuthenticated={openDashboard} onHome={goHome} />
  if (!user) return <div className="auth-loading"><BrandMark /><span>Opening your workspace…</span></div>

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => setTab('Overview')} aria-label="Open overview"><div className="brand-mark"><BrandMark /></div><div><strong>PlacementGap</strong><small>CAREER WORKSPACE</small></div></button>
      <div className="sidebar-section"><span className="eyebrow">YOUR WORKSPACE</span>{nav.map(item => <span className="sidebar-item-wrap" key={item}>{item === 'Roles' && <span className="sidebar-group-label">TARGET & COMPARE</span>}{item === 'Roadmap' && <span className="sidebar-group-label">BUILD & PRACTICE</span>}{item === 'Application Kit' && <span className="sidebar-group-label">CAREER LAUNCH</span>}{item === 'Trace' && <span className="sidebar-group-label">SYSTEM</span>}<button className={`nav-item ${tab === item ? 'selected' : ''}`} onClick={() => setTab(item)} aria-label={item} title={item}><span className="nav-icon">{item === 'Overview' ? '⌂' : item === 'Analyze' ? '↗' : item === 'Roadmap' ? '▤' : item === 'Roles' ? '◉' : item === 'Skill Lab' ? '⌁' : item === 'Portfolio' ? '▧' : item === 'Application Kit' ? '✳' : item === 'Resources' ? '↗' : item === 'Market' ? '◫' : item === 'Applications' ? '▥' : item === 'Trace' ? '⌕' : item === 'Compare' ? '⇄' : '▦'}</span>{item}{item === 'Analyze' && run?.status === 'awaiting_approval' && <i className="nav-alert" />}</button></span>)}</div>
      <div className="sidebar-bottom"><div className="signed-in-card"><span className="avatar-initials">{user.full_name.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase()}</span><div><b>{user.full_name}</b><small>{user.email}</small></div></div><button className="signout-button" onClick={() => void signOut()}>Sign out <span>↗</span></button><span className="connection"><i /> API connection</span><small>v1.0 · fixture mode</small></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div><span className="eyebrow">YOUR CAREER WORKSPACE / {tab.toUpperCase()}</span><h1>{tab === 'Overview' ? `Welcome, ${user.full_name.split(' ')[0]}` : tab === 'Analyze' ? 'Build a learning plan' : tab === 'Trace' ? 'Evidence & run trace' : tab === 'Compare' ? 'Compare your runs' : tab === 'Evals' ? 'System quality' : tab === 'Roles' ? 'Target role shortlist' : tab === 'Roadmap' ? 'Your adaptive roadmap' : tab === 'Skill Lab' ? 'Skill checks & interview practice' : tab === 'Portfolio' ? 'Projects & portfolio proof' : tab === 'Application Kit' ? 'Your application materials' : tab === 'Resources' ? 'Learning resources' : tab === 'Market' ? 'Role context' : 'Application pipeline'}</h1></div><div className="top-metrics"><span><small>LAST ANALYSIS</small><b>{run ? run.run_id.slice(0, 8) : 'Not started'}</b></span><span><small>MODEL SPEND</small><b>${cost.toFixed(4)}</b></span></div></header>
      <div className="content-area">
        {tab === 'Overview' && <Overview user={user} run={run} onNavigate={setTab} onSignOut={() => void signOut()} />}
         {tab === 'Analyze' && <div className="run-layout"><div className="left-column"><form className="panel run-form" onSubmit={start}><div className="panel-title"><div><span className="eyebrow light-eyebrow">YOUR NEXT ROLE</span><h2>Student record + job description</h2></div><span className="step-label">01 / ANALYZE</span></div>
          <label className="field-label">Student profile ID<input value={studentId} onChange={event => setStudentId(event.target.value)} placeholder="Your profile ID" /></label>
           <label className="field-label">Transcript, resume, or project record<textarea rows={7} value={profile} onChange={event => { setProfile(event.target.value); setProfileFile(null) }} placeholder={'Add course names and grades, then describe projects and your contribution.\n\nExample: Built a REST API with Python and PostgreSQL; wrote tests and deployed it with Docker.'} required={!profileFile} /></label>
           <p className="input-guidance">Specific course names, project outcomes, tools, and your role help the report distinguish familiarity from hands-on experience.</p>
           <label className="file-drop"><span className="file-icon">↥</span><span><b>{profileFile ? profileFile.filename : 'Attach transcript or resume'}</b><small>PDF, DOCX, or text. Scanned PDFs use OCR when available.</small></span><input type="file" accept=".pdf,.docx,.txt" onChange={event => void upload(event.target.files?.[0])} /></label>
          <div className="section-divider"><span>THE ROLE YOU WANT</span></div>
           <label className="field-label">Job description<textarea rows={5} value={jd} onChange={event => setJd(event.target.value)} placeholder="Paste the complete job description so required and preferred skills can be compared." /></label>
          <div className="three-fields"><label className="field-label">Live JD URL<input type="url" value={jdUrl} onChange={event => setJdUrl(event.target.value)} placeholder="https://company.com/careers/role" /></label><label className="field-label">Role title<input value={role} onChange={event => setRole(event.target.value)} placeholder="e.g. Backend Engineer" /></label><label className="field-label">Company<input value={company} onChange={event => setCompany(event.target.value)} placeholder="Company name (optional)" /></label></div>
          <div className="two-fields"><label className="field-label">Plan horizon (weeks)<input type="number" min="1" max="104" value={weeks} onChange={event => setWeeks(Number(event.target.value))} /></label><label className="field-label">Available hours / week<input type="number" min="0.5" max="100" step="0.5" value={hours} onChange={event => setHours(Number(event.target.value))} /></label></div>
          {error && <div className="error-box">{error}</div>}<button className="button primary start-button" disabled={loading}>{loading ? <><i className="spinner" /> Analyzing your record…</> : <>Find my real gaps <span>↗</span></>}</button>
        </form>
        {run && <section className="panel results-panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">ROLE SNAPSHOT</span><h2>{run.role || role}</h2></div><span className={`pill ${run.status}`}>{run.status.replaceAll('_', ' ')}</span></div><div className="result-stats"><span><b>{run.gaps?.length ?? 0}</b><small>requirements</small></span><span><b>{run.plan?.total_hours ?? 0}h</b><small>scheduled</small></span><span><b>{run.plan?.deferred?.length ?? 0}</b><small>deferred</small></span><span><b>{run.discovery_tier || 'pending'}</b><small>JD source tier</small></span></div>
          {run.degraded && <div className="warning-box">Degraded run: {run.degraded_reasons?.join(' ')}</div>}
          {run.status === 'awaiting_approval' && <ApprovalGate runId={run.run_id} plan={run.plan} onSubmitted={onApproval} />}
          {run.status === 'completed' && <div className="report-links"><a className="button secondary" href={api(`/runs/${run.run_id}/report.md`)} target="_blank" rel="noreferrer">Markdown</a><a className="button secondary" href={api(`/runs/${run.run_id}/report.pdf`)} target="_blank" rel="noreferrer">Download PDF</a><a className="button secondary" href={api(`/runs/${run.run_id}/report.json`)} target="_blank" rel="noreferrer">report.json</a></div>}
           <div className="gap-list">{run.gaps?.slice(0, 8).map(gap => <div className="gap-row" key={gap.skill_id}><span className={`verdict-dot ${gap.verdict}`} /><b>{gap.canonical_name}</b><span className={`verdict ${gap.verdict}`}>{gap.verdict}</span><small>Δ {gap.level_delta}</small></div>)}</div>
         </section>}{run && <EvidenceLedger run={run} />}</div><aside className="analysis-side"><section className="panel analysis-guide"><span className="eyebrow light-eyebrow">{run ? 'LATEST ANALYSIS' : 'HOW TO GET A USEFUL PLAN'}</span><h2>{run ? (run.degraded ? 'This result needs better source detail.' : 'Your analysis is ready to review.') : 'Start with evidence, not keywords.'}</h2><p>{run ? (run.degraded ? 'The report found too little structured information to make reliable skill recommendations. Add a fuller record and job description before relying on this result.' : `${run.gaps?.length ?? 0} requirements reviewed with a ${run.plan?.total_hours ?? 0} hour plan.`) : 'A short list of technologies is not enough to estimate your level. Describe what you studied, built, and owned.'}</p><div className="analysis-guide-list"><article><span>01</span><div><b>Your record</b><small>Course names, projects, tools, and your contribution.</small></div></article><article><span>02</span><div><b>The target role</b><small>A full job description, a live link, or a specific role and company.</small></div></article><article><span>03</span><div><b>Your time budget</b><small>Set a realistic number of weeks and study hours.</small></div></article></div><div className="analysis-guide-footer"><span>Detailed node activity and prompts are kept in Trace.</span>{run && <button className="button secondary" onClick={() => setTab('Trace')}>Open Trace <span>↗</span></button>}</div></section></aside></div>}
        {tab === 'Trace' && <div className="trace-view"><div className="panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">CURRENT ANALYSIS</span><h2>{run?.run_id ?? 'Your trace will appear here'}</h2></div><button className="button secondary" onClick={() => run && void refresh(run.run_id)} disabled={!run}>Refresh</button></div><p className="muted">Follow each node and tool call with its prompt version, source, token use, model, latency, retries, and cost.</p></div><TracePanel traces={traces} /><RunGraph events={events} status={run?.status ?? 'idle'} /></div>}
        {tab === 'Compare' && <RunDiff />}{tab === 'Evals' && <EvalDashboard />}
        <CareerStudio active={careerTabs.includes(tab as CareerTab) ? tab as CareerTab : null} user={user} run={run} selectedTargetId={selectedTargetId} onTargetLinked={() => setSelectedTargetId(null)} onAnalyzeRole={analyzeSavedRole} />
      </div>
    </main>
  </div>
}
