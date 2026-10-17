import type { PlacementUser } from './AuthPage'
import type { RunState } from './types'

const workspace = [
  { tab: 'Analyze', number: '01', title: 'Build a learning plan', text: 'Compare your student record with a job description and map the skills to build.', icon: '↗', tone: 'oat' },
  { tab: 'Trace', number: '02', title: 'Follow the evidence', text: 'Inspect node steps, source passages, tool results, tokens, and model spend.', icon: '⌕', tone: 'clay' },
  { tab: 'Compare', number: '03', title: 'Compare two runs', text: 'See how a new role or updated profile changes your gaps and next steps.', icon: '⇄', tone: 'olive' },
  { tab: 'Evals', number: '04', title: 'Review system quality', text: 'Open extraction, groundedness, plan validity, latency, and recovery metrics.', icon: '▥', tone: 'sky' },
]

export default function Overview({ user, run, onNavigate, onSignOut }: {
  user: PlacementUser
  run: RunState | null
  onNavigate: (tab: 'Analyze' | 'Trace' | 'Compare' | 'Evals') => void
  onSignOut: () => void
}) {
  const firstName = user.full_name.split(' ')[0] || 'there'
  const missing = run?.gaps?.filter(gap => gap.verdict !== 'has').length ?? 0
  const totalHours = run?.plan?.total_hours ?? 0

  return <div className="overview-page">
    <section className="welcome-panel">
      <div className="welcome-copy"><span className="eyebrow">YOUR CAREER WORKSPACE</span><h2>Good morning, {firstName}.</h2><p>Let’s turn the experience you have into a clear next step.</p><button className="pill-action dark" onClick={() => onNavigate('Analyze')}>Start a new analysis <span>↗</span></button></div>
      <div className="welcome-illustration"><div className="welcome-orbit" /><div className="welcome-note"><span>✳</span><div><small>ONE ROLE AT A TIME</small><b>Clarity, then<br />a doable plan.</b></div></div><div className="welcome-ticket"><small>YOUR NEXT MOVE</small><b>Start with what you know.</b><span>PLACEMENTGAP · 01</span></div></div>
      <span className="welcome-index">PG / YOUR WORKSPACE</span>
    </section>

    <div className="workspace-overline"><span className="eyebrow light-eyebrow">YOUR SNAPSHOT</span><button className="profile-chip" onClick={onSignOut}><span className="avatar-initials">{user.full_name.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase()}</span><span>{user.full_name}</span><i>↗</i></button></div>
    <section className="overview-stats">
      <article className="overview-stat"><span>LAST TARGET ROLE</span><b>{run?.role || 'Not set yet'}</b><small>{run ? run.discovery_tier.replaceAll('_', ' ') : 'Choose a role to begin'}</small></article>
      <article className="overview-stat"><span>SKILLS TO BUILD</span><b>{run ? String(missing).padStart(2, '0') : '—'}</b><small>{run ? 'grounded in your record' : 'shown after your first analysis'}</small></article>
      <article className="overview-stat"><span>PLANNED LEARNING</span><b>{run ? `${totalHours}h` : '—'}</b><small>{run ? `${run.plan?.weeks.length ?? 0} active weeks` : 'fit to your weekly hours'}</small></article>
      <article className="overview-stat"><span>RUN STATUS</span><b className={`overview-status ${run?.status === 'completed' ? 'complete' : ''}`}>{run ? run.status.replaceAll('_', ' ') : 'Ready when you are'}</b><small>{run?.degraded ? 'some findings are degraded' : 'your work stays organized here'}</small></article>
    </section>

    <div className="section-heading compact-heading"><div><span className="eyebrow light-eyebrow">MAKE YOUR NEXT MOVE</span><h2>Your workspace,<br /><em>in good order.</em></h2></div><p>Each part of your analysis has its place. Start with the role, then follow the evidence and plan.</p></div>
    <section className="workspace-grid">{workspace.map(item => <button className={`workspace-card ${item.tone}`} key={item.number} onClick={() => onNavigate(item.tab as 'Analyze' | 'Trace' | 'Compare' | 'Evals')}><span className="workspace-card-top"><small>{item.number} / WORKSPACE</small><i>{item.icon}</i></span><span className="workspace-card-title">{item.title}</span><span className="workspace-card-copy">{item.text}</span><span className="workspace-card-link">OPEN SECTION <b>↗</b></span></button>)}</section>

    <section className="overview-bottom">
      <div className="recent-panel"><div className="recent-panel-head"><div><span className="eyebrow light-eyebrow">LATEST ANALYSIS</span><h3>{run?.role || 'Your first role starts here'}</h3></div>{run && <span className={`status-pill ${run.status === 'completed' ? 'complete' : ''}`}>{run.status.replaceAll('_', ' ')}</span>}</div>
        {run ? <><p className="muted">{run.gaps?.length ?? 0} requirements checked · {totalHours} hours in the proposed plan</p><div className="recent-gaps">{run.gaps?.slice(0, 5).map(gap => <div className="recent-gap" key={gap.skill_id}><span className={`recent-dot ${gap.verdict}`} /><b>{gap.canonical_name}</b><span>{gap.verdict === 'has' ? 'Evidence found' : gap.verdict === 'partial' ? 'Build confidence' : 'Next to learn'}</span><small>↗</small></div>)}</div><button className="text-action warm" onClick={() => onNavigate('Analyze')}>Open the full analysis →</button></> : <><p className="muted">Your analysis will appear here with the skill evidence, verdicts, and hour-budgeted plan together.</p><button className="text-action warm" onClick={() => onNavigate('Analyze')}>Choose a role to get started →</button></>}
      </div>
      <aside className="workspace-tip"><div className="tip-symbol">✳</div><span className="eyebrow">A SMALL REMINDER</span><h3>Your record is the starting point.</h3><p>Courses, projects, and experience carry different kinds of evidence. PlacementGap keeps those distinctions visible.</p><button onClick={() => onNavigate('Analyze')}>Add or update your profile <span>↗</span></button></aside>
    </section>
  </div>
}
