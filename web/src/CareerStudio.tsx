import { useEffect, useMemo, useRef, useState } from 'react'
import type { PlacementUser } from './AuthPage'
import { careerTabs, completedTaskKey, emptyWorkspace, type CareerTab, type SavedRole, type WorkspaceData } from './careerTypes'
import type { RunState } from './types'

const api = (path: string) => `${import.meta.env.VITE_API_URL ?? ''}${path}`
const now = () => new Date().toISOString()
const makeId = () => crypto.randomUUID()
const dateLabel = (value: string) => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

function PageHeading({ kicker, title, body, action }: { kicker: string; title: string; body: string; action?: React.ReactNode }) {
  return <header className="studio-heading"><div><span className="eyebrow light-eyebrow">{kicker}</span><h2>{title}</h2><p>{body}</p></div>{action && <div className="studio-heading-action">{action}</div>}</header>
}

function RunEvidence({ run }: { run: RunState | null }) {
  if (!run) return <div className="studio-empty"><span className="empty-orbit">✳</span><h3>Your current analysis will power this workspace.</h3><p>Start with a resume and a specific role. Your evidence, gaps, and plan will appear across these sections.</p></div>
  return null
}

type Props = {
  active: CareerTab | null
  user: PlacementUser
  run: RunState | null
  selectedTargetId: string | null
  onTargetLinked: () => void
  onAnalyzeRole: (role: SavedRole) => void
}

export default function CareerStudio({ active, user, run, selectedTargetId, onTargetLinked, onAnalyzeRole }: Props) {
  const [workspace, setWorkspace] = useState<WorkspaceData>(emptyWorkspace)
  const [loaded, setLoaded] = useState(false)
  const [saveState, setSaveState] = useState<'loading' | 'saved' | 'saving' | 'offline'>('loading')
  const linkedRun = useRef('')
  const saveQueue = useRef<Promise<void>>(Promise.resolve())
  const localKey = `placementgap:workspace:${user.id}`

  useEffect(() => {
    let cancelled = false
    setLoaded(false)
    setSaveState('loading')
    void fetch(api('/workspace'), { credentials: 'include' }).then(async response => {
      if (!response.ok) throw new Error('Workspace service unavailable')
      const serverData = await response.json() as WorkspaceData
      if (cancelled) return
      const serverHasData = serverData.saved_roles.length > 0 || serverData.roadmap.completed_task_ids.length > 0 || serverData.skill_checks.length > 0 || serverData.projects.length > 0 || serverData.artifacts.length > 0 || serverData.applications.length > 0 || serverData.application_packs.length > 0 || serverData.interview_sessions.length > 0
      const backup = localStorage.getItem(localKey)
      const localData = backup ? JSON.parse(backup) as WorkspaceData : null
      const initialData = !serverHasData && localData ? localData : { ...emptyWorkspace, ...serverData }
      const initial = { ...initialData, saved_roles: initialData.saved_roles.map(role => ({ ...role, url: role.url ?? '' })) }
      setWorkspace(initial)
      setSaveState('saved')
      setLoaded(true)
    }).catch(() => {
      if (cancelled) return
      try {
        const backup = localStorage.getItem(localKey)
        setWorkspace(backup ? { ...emptyWorkspace, ...JSON.parse(backup) as WorkspaceData } : emptyWorkspace)
      } catch { setWorkspace(emptyWorkspace) }
      setSaveState('offline')
      setLoaded(true)
    })
    return () => { cancelled = true }
  }, [user.id])

  useEffect(() => {
    if (!loaded) return
    const timer = window.setTimeout(() => {
      setSaveState('saving')
      try { localStorage.setItem(localKey, JSON.stringify(workspace)) } catch { /* the server remains the primary store */ }
      saveQueue.current = saveQueue.current.then(async () => {
        const response = await fetch(api('/workspace'), {
          method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(workspace),
        })
        if (!response.ok) throw new Error('Workspace save failed')
        setSaveState('saved')
      }).catch(() => setSaveState('offline'))
    }, 450)
    return () => window.clearTimeout(timer)
  }, [workspace, loaded, localKey])

  useEffect(() => {
    if (!loaded || !run || run.status !== 'completed' || linkedRun.current === run.run_id) return
    const title = run.role || run.job?.role || 'Saved role'
    const company = run.company || run.job?.company || ''
    const snapshot = run.gaps.map(gap => ({ skill_id: gap.skill_id, canonical_name: gap.canonical_name, verdict: gap.verdict, level_delta: gap.level_delta, priority_score: gap.priority_score }))
    setWorkspace(current => {
      const index = current.saved_roles.findIndex(item => item.id === selectedTargetId || (item.title.toLowerCase() === title.toLowerCase() && item.company.toLowerCase() === company.toLowerCase()))
      const saved: SavedRole = {
        id: index >= 0 ? current.saved_roles[index].id : selectedTargetId || makeId(),
        title, company, location: index >= 0 ? current.saved_roles[index].location : '',
        url: run.jd_url ?? '', description: run.job?.text ?? '', run_id: run.run_id, gaps: snapshot,
        created_at: index >= 0 ? current.saved_roles[index].created_at : now(),
      }
      const savedRoles = [...current.saved_roles]
      if (index >= 0) savedRoles[index] = saved
      else savedRoles.unshift(saved)
      return { ...current, saved_roles: savedRoles.slice(0, 30) }
    })
    linkedRun.current = run.run_id
    onTargetLinked()
  }, [loaded, run?.run_id, run?.status, selectedTargetId])

  const update = (recipe: (current: WorkspaceData) => WorkspaceData) => setWorkspace(current => recipe(current))
  if (!active) return null

  const page = (() => {
    switch (active) {
      case 'Roles': return <RolesPage workspace={workspace} update={update} run={run} onAnalyzeRole={onAnalyzeRole} />
      case 'Roadmap': return <RoadmapPage workspace={workspace} update={update} run={run} />
      case 'Skill Lab': return <SkillLabPage workspace={workspace} update={update} run={run} />
      case 'Portfolio': return <PortfolioPage workspace={workspace} update={update} run={run} />
      case 'Application Kit': return <ApplicationKitPage workspace={workspace} update={update} run={run} />
      case 'Resources': return <ResourcesPage run={run} />
      case 'Market': return <MarketPage run={run} />
      case 'Applications': return <ApplicationsPage workspace={workspace} update={update} run={run} />
      default: return null
    }
  })()
  return <div className="career-studio" key={active}>
    <div className="studio-save-state"><span className={`save-indicator ${saveState}`} />{saveState === 'loading' ? 'Opening your workspace' : saveState === 'saving' ? 'Saving your changes' : saveState === 'offline' ? 'Offline · changes backed up in this browser' : 'Your workspace is saved'}</div>
    <div className="studio-subnav" aria-label="Career tools">{careerTabs.map((tab, index) => <span className={tab === active ? 'active' : ''} key={tab}>{String(index + 1).padStart(2, '0')} {tab}</span>)}</div>
    <div key={active} className="studio-page-enter">{page}</div>
  </div>
}

function RolesPage({ workspace, update, run, onAnalyzeRole }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null; onAnalyzeRole: (role: SavedRole) => void }) {
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [roleUrl, setRoleUrl] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const addRole = (event: React.FormEvent) => {
    event.preventDefault()
    if (!title.trim() || (!description.trim() && !roleUrl.trim())) { setError('Add a role title and either its full job description or a job link.'); return }
    if (roleUrl.trim() && !/^https?:\/\//i.test(roleUrl.trim())) { setError('Use a complete https:// or http:// job link.'); return }
    const role: SavedRole = { id: makeId(), title: title.trim(), company: company.trim(), location: location.trim(), url: roleUrl.trim(), description: description.trim(), run_id: null, gaps: [], created_at: now() }
    update(current => ({ ...current, saved_roles: [role, ...current.saved_roles].slice(0, 30) }))
    setTitle(''); setCompany(''); setLocation(''); setRoleUrl(''); setDescription(''); setError('')
  }
  const skillNames = [...new Set(workspace.saved_roles.flatMap(role => role.gaps.map(gap => gap.canonical_name)))].slice(0, 10)
  return <>
    <PageHeading kicker="OPPORTUNITY MAP · 01" title="Compare the roles you’re considering." body="Save real job descriptions, analyze each against the same profile, and see which gaps repeat across opportunities." action={<span className="metric-chip">{workspace.saved_roles.length} / 30 saved</span>} />
    <div className="roles-layout">
      <section className="panel role-add-panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">ADD A TARGET</span><h2>Save a role to compare</h2></div><span className="panel-index">01</span></div>
        <form onSubmit={addRole} className="studio-form"><div className="studio-field-row"><label>Role title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="Backend Engineer" required maxLength={120} /></label><label>Company<input value={company} onChange={event => setCompany(event.target.value)} placeholder="Company name" maxLength={120} /></label></div><label>Location (optional)<input value={location} onChange={event => setLocation(event.target.value)} placeholder="Remote · New York · Bengaluru" maxLength={120} /></label><label>Live job link (optional)<input type="url" value={roleUrl} onChange={event => setRoleUrl(event.target.value)} placeholder="https://company.com/careers/role" maxLength={2_048} /></label><label>Complete job description<textarea value={description} onChange={event => setDescription(event.target.value)} placeholder="Paste the full description, or add a live link above." rows={5} maxLength={12_000} /></label>{error && <div className="error-box">{error}</div>}<button className="button primary">Save target role <span>↗</span></button></form>
      </section>
      <section className="role-stack"><div className="studio-section-head"><div><span className="eyebrow light-eyebrow">YOUR SHORTLIST</span><h3>Role snapshots</h3></div><span>{workspace.saved_roles.length} targets</span></div>
        {!workspace.saved_roles.length && <div className="panel studio-empty compact"><span className="empty-orbit">✳</span><h3>No roles saved yet</h3><p>Add a job description here, then analyze it with the same resume you used before.</p></div>}
        {workspace.saved_roles.map((role, index) => {
          const has = role.gaps.filter(gap => gap.verdict === 'has').length
          const percent = role.gaps.length ? Math.round(has / role.gaps.length * 100) : 0
          const latest = role.run_id === run?.run_id
          return <article className="role-card" key={role.id} style={{ animationDelay: `${index * 55}ms` }}><div className="role-card-top"><span className="role-marker">{String(index + 1).padStart(2, '0')}</span><div className="role-card-title"><h3>{role.title}</h3><p>{[role.company, role.location].filter(Boolean).join(' · ') || 'Company not specified'}</p></div><button className="icon-button" aria-label={`Remove ${role.title}`} title="Remove target" onClick={() => update(current => ({ ...current, saved_roles: current.saved_roles.filter(item => item.id !== role.id) }))}>×</button></div><div className="role-card-stats">{role.run_id ? <><span><b>{percent}%</b><small>requirements evidenced</small></span><span><b>{role.gaps.filter(gap => gap.verdict !== 'has').length}</b><small>gaps to work on</small></span><span><b>{role.gaps.length}</b><small>reviewed</small></span></> : <><span><b>—</b><small>no analysis yet</small></span><span><b>Ready</b><small>source saved below</small></span></>}</div><div className="role-progress"><i style={{ width: `${percent}%` }} /></div><div className="role-card-foot"><span>{role.run_id ? `Analysis · ${role.run_id.slice(0, 8)}${latest ? ' · current' : ''}` : `Saved ${dateLabel(role.created_at)}`}</span><div className="role-card-actions">{role.url && <a href={role.url} target="_blank" rel="noreferrer">Job posting ↗</a>}<button className="text-action warm" onClick={() => onAnalyzeRole(role)}>{role.run_id ? 'Re-analyze' : 'Analyze role'} ↗</button></div></div></article>
        })}
      </section>
    </div>
    {skillNames.length > 0 && <section className="panel role-matrix"><div className="panel-title"><div><span className="eyebrow light-eyebrow">CROSS-ROLE VIEW</span><h2>Skills that change your options</h2></div><span className="count-badge">{workspace.saved_roles.filter(role => role.run_id).length} analyzed</span></div><div className="matrix-scroll"><table className="skill-matrix"><thead><tr><th>Skill</th>{workspace.saved_roles.map(role => <th key={role.id}>{role.title}<small>{role.company || 'Saved role'}</small></th>)}</tr></thead><tbody>{skillNames.map(skill => <tr key={skill}><th>{skill}</th>{workspace.saved_roles.map(role => { const result = role.gaps.find(gap => gap.canonical_name === skill); return <td key={role.id}>{result ? <span className={`verdict ${result.verdict}`}>{result.verdict}</span> : <span className="matrix-na">—</span>}</td> })}</tr>)}</tbody></table></div><p className="muted">A “has” verdict means the analyzed record contained evidence for that requirement. Saved roles without an analysis are not included in a fit comparison.</p></section>}
    <RunEvidence run={run} />
  </>
}

type PlanTask = { skill_id: string; canonical_name: string; hours: number; outcome: string; prerequisite_ids: string[]; resources: Array<{ title: string; url: string; kind: string }>; originalWeek: number }
type ScheduledTask = PlanTask & { assignments: Array<{ week: number; hours: number }> }

function rebalance(tasks: PlanTask[], completed: Set<string>, completedSkills: Set<string>, startWeek: number, weekCount: number, capacity: number) {
  const pending = tasks.filter(task => !completed.has(task.skill_id))
  const assigned = new Map<string, ScheduledTask>()
  const blocked: PlanTask[] = []
  const loads = new Map<number, number>()
  let guard = pending.length + 1
  while (pending.length && guard-- > 0) {
    const readyIndex = pending.findIndex(task => task.prerequisite_ids.every(id => completedSkills.has(id) || !tasks.some(candidate => candidate.skill_id === id) || assigned.has(id)))
    if (readyIndex < 0) { blocked.push(...pending.splice(0)); break }
    const task = pending.splice(readyIndex, 1)[0]
    if (!task) continue
    const requiredEnd = Math.max(startWeek - 1, ...task.prerequisite_ids.map(id => {
      const dependency = assigned.get(id)
      return dependency?.assignments.at(-1)?.week ?? startWeek - 1
    }))
    let remaining = task.hours
    const assignments: Array<{ week: number; hours: number }> = []
    for (let week = requiredEnd + 1; week <= Math.max(weekCount, requiredEnd + 1); week += 1) {
      const free = Math.max(0, capacity - (loads.get(week) ?? 0))
      const hours = Math.min(free, remaining)
      if (hours > 0) { assignments.push({ week, hours }); loads.set(week, (loads.get(week) ?? 0) + hours); remaining = Math.round((remaining - hours) * 100) / 100 }
      if (remaining <= 0) break
    }
    if (remaining > 0) blocked.push(task)
    else assigned.set(task.skill_id, { ...task, assignments })
  }
  const weeks = new Map<number, ScheduledTask[]>()
  for (const task of assigned.values()) for (const assignment of task.assignments) weeks.set(assignment.week, [...(weeks.get(assignment.week) ?? []), { ...task, assignments: [assignment] }])
  return { weeks: [...weeks.entries()].sort((a, b) => a[0] - b[0]), blocked }
}

function RoadmapPage({ workspace, update, run }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null }) {
  const [replanning, setReplanning] = useState(false)
  const [startWeek, setStartWeek] = useState(1)
  if (!run?.plan) return <><PageHeading kicker="LEARNING RHYTHM · 02" title="A plan you can keep adjusting." body="Check off completed work. If a week slips, rebuild the remaining schedule around your current time budget." /><RunEvidence run={run} /></>
  const completed = new Set(workspace.roadmap.completed_task_ids)
  const allTasks: PlanTask[] = run.plan.weeks.flatMap(week => week.items.map(item => ({ skill_id: item.skill_id, canonical_name: item.canonical_name, hours: item.hours, outcome: item.outcome, prerequisite_ids: item.prerequisite_ids, resources: item.resources, originalWeek: week.week })))
  const completeSkills = new Set([...run.plan.satisfied_skills, ...run.gaps.filter(gap => gap.verdict === 'has').map(gap => gap.skill_id), ...allTasks.filter(item => completed.has(completedTaskKey(run.run_id, item.skill_id))).map(item => item.skill_id)])
  const schedule = replanning ? rebalance(allTasks, new Set([...completed].map(key => key.startsWith(`${run.run_id}:`) ? key.slice(run.run_id.length + 1) : key)), completeSkills, startWeek, run.weeks, run.hours_per_week).weeks : run.plan.weeks.map(week => [week.week, week.items.map(item => ({ ...item, originalWeek: week.week, assignments: [{ week: week.week, hours: item.hours }] }))] as const)
  const progress = allTasks.length ? Math.round(allTasks.filter(task => completed.has(completedTaskKey(run.run_id, task.skill_id))).length / allTasks.length * 100) : 0
  return <>
    <PageHeading kicker="LEARNING RHYTHM · 02" title="Make the plan fit your actual week." body={`${run.role || 'Your target role'} · ${run.plan.total_hours} planned hours across ${run.weeks} weeks. Progress and schedule adjustments are saved to your account.`} action={<div className="roadmap-progress"><b>{progress}%</b><span>complete</span><i><em style={{ width: `${progress}%` }} /></i></div>} />
    <section className="panel roadmap-controls"><div><span className="eyebrow light-eyebrow">ADAPTIVE PLAN</span><h3>{replanning ? 'Remaining work redistributed by capacity.' : 'Your approved week-by-week plan.'}</h3><p>Prerequisite skills remain ahead of dependent work. Weekly study never exceeds {run.hours_per_week} hours.</p></div><div className="roadmap-control-actions"><label>Start replan from week<select value={startWeek} onChange={event => setStartWeek(Number(event.target.value))}>{Array.from({ length: Math.max(run.weeks, 1) }, (_, index) => <option key={index + 1} value={index + 1}>Week {index + 1}</option>)}</select></label><button className="button secondary" onClick={() => setReplanning(value => !value)}>{replanning ? 'Show original plan' : 'Re-plan remaining work'}</button></div></section>
    <div className="roadmap-week-list">{schedule.map(([weekNumber, tasks]) => <section className="roadmap-week panel" key={weekNumber}><div className="week-number"><small>WEEK</small><b>{String(weekNumber).padStart(2, '0')}</b><span>{tasks.reduce((sum, task) => sum + (task.assignments[0]?.hours ?? task.hours), 0).toFixed(1)}h</span></div><div className="week-tasks">{tasks.map((task, index) => { const key = completedTaskKey(run.run_id, task.skill_id); const done = completed.has(key); const hours = task.assignments[0]?.hours ?? task.hours; return <article className={`roadmap-task ${done ? 'done' : ''}`} key={`${task.skill_id}-${index}`}><label className="task-check"><input type="checkbox" checked={done} onChange={event => update(current => ({ ...current, roadmap: { ...current.roadmap, completed_task_ids: event.target.checked ? [...new Set([...current.roadmap.completed_task_ids, key])] : current.roadmap.completed_task_ids.filter(id => id !== key) } }))} /><span /></label><div className="task-copy"><b>{task.canonical_name}</b><p>{task.outcome}</p>{task.prerequisite_ids.length > 0 && <small>Prerequisites first · {task.prerequisite_ids.length} linked</small>}{task.resources.slice(0, 2).map(resource => <a key={resource.url} href={resource.url} target="_blank" rel="noreferrer">{resource.title} ↗</a>)}</div><span className="task-time">{hours.toFixed(1)} h</span></article> })}{!tasks.length && <p className="muted">No tasks scheduled for this week.</p>}</div></section>)}</div>
    {replanning && <div className="studio-note">The adaptive preview is deterministic and budget-capped; your approved run stays unchanged until you choose a new analysis.</div>}
  </>
}

type Question = { question: string; choices: string[]; answer: number; explanation: string }
const quizBank: Record<string, { name: string; questions: Question[] }> = {
  python: { name: 'Python', questions: [
    { question: 'What does a context manager most directly help with?', choices: ['Cleaning up a resource reliably', 'Making a function pure', 'Running a loop faster', 'Converting a list to a tuple'], answer: 0, explanation: 'A context manager centralizes setup and cleanup, even if the block raises an exception.' },
    { question: 'Why can a mutable default argument cause bugs?', choices: ['It is recreated on every call', 'The same object can be reused between calls', 'Python freezes it after import', 'It changes the function name'], answer: 1, explanation: 'Default values are evaluated once when the function is defined.' },
    { question: 'When is a generator useful?', choices: ['When all values must be indexed repeatedly', 'When values can be produced as they are consumed', 'Only for parallel code', 'To guarantee sorted output'], answer: 1, explanation: 'Generators can stream values and avoid keeping the whole sequence in memory.' },
  ] },
  git: { name: 'Git', questions: [
    { question: 'What does `git revert` do?', choices: ['Deletes the last commit from history', 'Creates a new commit that reverses earlier changes', 'Moves the branch pointer without a commit', 'Removes untracked files'], answer: 1, explanation: 'Revert is history-safe for shared branches because it records an inverse commit.' },
    { question: 'What does a merge conflict mean?', choices: ['Git found overlapping changes it cannot combine automatically', 'The remote is offline', 'A commit is unsigned', 'The branch has no upstream'], answer: 0, explanation: 'You resolve the conflicting sections, then stage and commit the resolution.' },
    { question: 'Which command shows changed files and staging state?', choices: ['git status', 'git stash', 'git tag', 'git init'], answer: 0, explanation: '`git status` summarizes the working tree and index.' },
  ] },
  docker: { name: 'Docker', questions: [
    { question: 'What is the main purpose of a Docker image?', choices: ['A running process', 'A reproducible template for creating containers', 'A shared host kernel', 'A virtual machine snapshot'], answer: 1, explanation: 'A container is created from an image; the image packages its filesystem and configuration.' },
    { question: 'Why use a multi-stage Docker build?', choices: ['To include build tools in production', 'To keep build dependencies out of the final runtime image', 'To run multiple containers in one image', 'To skip image layers'], answer: 1, explanation: 'The final stage can copy only built artifacts, reducing the runtime image.' },
    { question: 'What does a container health check report?', choices: ['Whether the app responds according to a configured probe', 'Whether the registry is public', 'The image license', 'Available host memory only'], answer: 0, explanation: 'A health check runs a probe and marks container health from its result.' },
  ] },
  sql: { name: 'SQL / PostgreSQL', questions: [
    { question: 'What does a database transaction provide?', choices: ['A way to guarantee only one table exists', 'A grouped operation with commit or rollback semantics', 'Automatic data compression', 'A cache that never expires'], answer: 1, explanation: 'Transactions let related changes succeed or fail together.' },
    { question: 'What is a common tradeoff of adding an index?', choices: ['Reads may improve, but writes and storage cost more', 'It removes the need for constraints', 'It makes every query constant time', 'It prevents duplicate rows automatically'], answer: 0, explanation: 'Indexes speed some lookups while adding storage and write maintenance.' },
    { question: 'Which join keeps all rows from the left table?', choices: ['INNER JOIN', 'LEFT JOIN', 'CROSS JOIN', 'NATURAL JOIN'], answer: 1, explanation: 'A left join retains unmatched left-side rows with nulls on the right.' },
  ] },
  testing: { name: 'Unit Testing', questions: [
    { question: 'What makes a unit test reliable?', choices: ['It depends on production data', 'It isolates behavior and gives the same result repeatedly', 'It verifies only source formatting', 'It runs after deployment'], answer: 1, explanation: 'Isolated deterministic tests give fast feedback and stable results.' },
    { question: 'What is a useful assertion?', choices: ['An assertion that checks the intended observable behavior', 'An assertion that every line ran', 'An assertion with no expected value', 'An assertion on private local variables only'], answer: 0, explanation: 'Assertions should describe the behavior contract, not internal implementation details.' },
    { question: 'What should a test double replace?', choices: ['The code under test', 'An external dependency when isolation is needed', 'The assertion', 'The test runner'], answer: 1, explanation: 'A mock or fake can isolate a network, clock, or service boundary.' },
  ] },
  react: { name: 'React', questions: [
    { question: 'What does a React key help identify?', choices: ['A list item across renders', 'A CSS class in Tailwind', 'The browser tab', 'An API secret'], answer: 0, explanation: 'Stable keys help React match list elements when items are inserted or reordered.' },
    { question: 'When should an effect cleanup function run?', choices: ['Before the effect reruns and when the component unmounts', 'Only after a failed render', 'Before every click handler', 'Only in production'], answer: 0, explanation: 'Cleanup releases subscriptions, timers, or other resources tied to the previous effect.' },
    { question: 'What is the usual purpose of lifting state up?', choices: ['Share state between components that need it', 'Move state to a CSS file', 'Avoid rendering children', 'Change a component into a server'], answer: 0, explanation: 'A common owner can coordinate values used by sibling components.' },
  ] },
  rest: { name: 'REST APIs', questions: [
    { question: 'What is the usual meaning of HTTP 201?', choices: ['A resource was created', 'The request was malformed', 'The caller is unauthorized', 'The server is unavailable'], answer: 0, explanation: '201 Created indicates a request created a resource.' },
    { question: 'Why should a POST retry be handled carefully?', choices: ['It may create the same side effect twice', 'POST has no body', 'It always changes a password', 'It cannot return errors'], answer: 0, explanation: 'Use idempotency keys or operation design to control duplicate side effects.' },
    { question: 'What should a 401 response generally indicate?', choices: ['Authentication is missing or invalid', 'The resource moved permanently', 'The server has no disk space', 'A successful delete'], answer: 0, explanation: '401 is the authentication challenge status; authorization failures are generally 403.' },
  ] },
}

function quizFor(skill: { skill_id: string; canonical_name: string }) {
  const text = `${skill.skill_id} ${skill.canonical_name}`.toLowerCase()
  const key = text.includes('python') ? 'python' : text.includes('git') ? 'git' : text.includes('docker') ? 'docker' : text.includes('postgres') || text.includes('sql') || text.includes('database') ? 'sql' : text.includes('test') ? 'testing' : text.includes('react') ? 'react' : text.includes('rest') || text.includes('api') ? 'rest' : ''
  return key ? quizBank[key] : null
}

function SkillLabPage({ workspace, update, run }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null }) {
  const gaps = run?.gaps ?? []
  const supported = gaps.map(gap => ({ skill_id: gap.skill_id, canonical_name: gap.canonical_name })).filter(skill => quizFor(skill))
  const [selectedId, setSelectedId] = useState(supported[0]?.skill_id ?? Object.keys(quizBank)[0] ?? 'python')
  const selected = supported.find(skill => skill.skill_id === selectedId) ?? supported[0] ?? { skill_id: selectedId, canonical_name: quizBank[selectedId]?.name ?? 'Python' }
  const quiz = quizFor(selected) ?? quizBank.python
  const [answers, setAnswers] = useState<number[]>([])
  const [confidence, setConfidence] = useState(3)
  const [result, setResult] = useState<{ correct: number; total: number } | null>(null)
  const [interviewIndex, setInterviewIndex] = useState(0)
  const [interviewAnswer, setInterviewAnswer] = useState('')
  const [interviewRating, setInterviewRating] = useState(3)
  const [interviewAnswers, setInterviewAnswers] = useState<Array<{ prompt: string; answer: string; self_rating: number }>>([])
  const [mode, setMode] = useState<'checkup' | 'interview'>('checkup')
  const skills = gaps.length ? gaps : [{ skill_id: 'python', canonical_name: 'Python', verdict: 'missing' as const }]
  const questions = useMemo(() => [
    `Tell me about a project where you used ${selected.canonical_name}. What did you build, what part did you own, and how did you verify it worked?`,
    `A feature using ${selected.canonical_name} is failing in production. What would you inspect first, and how would you narrow down the cause?`,
    `Describe a tradeoff you might face when using ${selected.canonical_name}. How would you choose between the options?`,
  ], [selected.canonical_name])
  const completed = () => setResult({ correct: quiz.questions.reduce((sum, question, item) => sum + (answers[item] === question.answer ? 1 : 0), 0), total: quiz.questions.length })
  const saveCheckup = () => {
    if (!result) return
    update(current => ({ ...current, skill_checks: [{ id: makeId(), skill_id: selected.skill_id, skill_name: selected.canonical_name, correct: result.correct, total: result.total, confidence, completed_at: now() }, ...current.skill_checks].slice(0, 200) }))
  }
  const saveInterviewAnswer = () => {
    if (!interviewAnswer.trim()) return
    setInterviewAnswers(current => [...current, { prompt: questions[interviewIndex] ?? questions[0] ?? '', answer: interviewAnswer.trim(), self_rating: interviewRating }])
    setInterviewAnswer(''); setInterviewIndex(value => (value + 1) % questions.length)
  }
  const finishInterview = () => {
    if (!interviewAnswers.length) return
    update(current => ({ ...current, interview_sessions: [{ id: makeId(), role: run?.role || 'Practice interview', answers: interviewAnswers, completed_at: now() }, ...current.interview_sessions].slice(0, 50) }))
    setInterviewAnswers([]); setInterviewIndex(0)
  }
  const starSignals = ['situation', 'task', 'action', 'result'].filter(signal => new RegExp(`\\b${signal}\\b`, 'i').test(interviewAnswer))
  return <>
    <PageHeading kicker="SKILL LAB · 03" title="Practice before the interview." body="Use short knowledge checks to find what to review, then rehearse role-specific answers with a private, self-review rubric." action={<span className="metric-chip">{workspace.skill_checks.length} saved checkups</span>} />
    <div className="studio-mode-tabs"><button className={mode === 'checkup' ? 'selected' : ''} onClick={() => setMode('checkup')}><span>01</span> Skill checkup</button><button className={mode === 'interview' ? 'selected' : ''} onClick={() => setMode('interview')}><span>02</span> Interview practice</button></div>
    {mode === 'checkup' ? <div className="lab-layout"><section className="panel quiz-panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">OBJECTIVE PRACTICE</span><h2>{quiz?.name ?? selected.canonical_name} checkup</h2></div><select value={selected.skill_id} onChange={event => { setSelectedId(event.target.value); setAnswers([]); setResult(null) }} aria-label="Choose a skill">{skills.map(skill => <option key={skill.skill_id} value={skill.skill_id}>{skill.canonical_name}</option>)}</select></div><div className="quiz-progress">{quiz.questions.map((question, index) => <i key={question.question} className={answers[index] !== undefined ? 'answered' : ''} />)}</div>{quiz.questions.map((question, index) => <fieldset className="quiz-question" key={question.question}><legend><span>{String(index + 1).padStart(2, '0')}</span>{question.question}</legend><div className="quiz-options">{question.choices.map((choice, choiceIndex) => <label className={answers[index] === choiceIndex ? 'chosen' : ''} key={choice}><input type="radio" name={`q-${index}`} checked={answers[index] === choiceIndex} onChange={() => setAnswers(current => { const next = [...current]; next[index] = choiceIndex; return next })} /><i>{String.fromCharCode(65 + choiceIndex)}</i><span>{choice}</span></label>)}</div>{result && <p className={`quiz-explanation ${answers[index] === question.answer ? 'correct' : 'review'}`}>{answers[index] === question.answer ? 'Correct · ' : 'Review · '}{question.explanation}</p>}</fieldset>)}<div className="quiz-footer"><label>How confident did you feel?<select value={confidence} onChange={event => setConfidence(Number(event.target.value))}><option value={1}>1 · Guessing</option><option value={2}>2 · Unsure</option><option value={3}>3 · Somewhat</option><option value={4}>4 · Confident</option><option value={5}>5 · Very confident</option></select></label>{result ? <><strong className="quiz-score">{result.correct}/{result.total} correct</strong><button className="button primary" onClick={saveCheckup}>Save result</button><button className="button secondary" onClick={() => { setAnswers([]); setResult(null) }}>Try again</button></> : <button className="button primary" disabled={answers.length < quiz.questions.length} onClick={completed}>Check answers</button>}</div><p className="muted fine-print">Practice only—not a certification or a change to the evidence-based gap verdict.</p></section><aside className="panel lab-aside"><span className="eyebrow light-eyebrow">RECENT PRACTICE</span><h3>Knowledge you can build on.</h3>{workspace.skill_checks.length ? workspace.skill_checks.slice(0, 6).map(check => <div className="check-history" key={check.id}><span className="mini-score">{Math.round(check.correct / check.total * 100)}%</span><div><b>{check.skill_name}</b><small>{check.correct} of {check.total} · confidence {check.confidence}/5</small></div></div>) : <p className="muted">Your saved results will show up here so you can spot what to review next.</p>}<div className="practice-signal"><span>✳</span><p>Combine a good answer with project evidence. The portfolio section helps you make that proof easy to find.</p></div></aside></div> : <div className="interview-layout"><section className="panel interview-panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">MOCK INTERVIEW · {run?.role || 'GENERAL PRACTICE'}</span><h2>Question {interviewIndex + 1} of {questions.length}</h2></div><span className="pill">LOCAL PRACTICE</span></div><div className="interview-prompt"><span>✳</span><p>{questions[interviewIndex]}</p></div><label className="studio-label">Draft your answer<textarea rows={8} value={interviewAnswer} onChange={event => setInterviewAnswer(event.target.value)} placeholder="Use a specific example. Explain what you did, why, and what changed." maxLength={5000} /></label><div className="interview-checklist"><b>Self-review signals</b>{['situation', 'task', 'action', 'result'].map(item => <span className={starSignals.includes(item) ? 'present' : ''} key={item}><i>{starSignals.includes(item) ? '✓' : '·'}</i>{item}</span>)}<small>Checks whether your draft explicitly names these story elements; it does not judge answer quality.</small></div><div className="quiz-footer"><label>How strong does this answer feel?<select value={interviewRating} onChange={event => setInterviewRating(Number(event.target.value))}>{[1,2,3,4,5].map(value => <option key={value} value={value}>{value} / 5</option>)}</select></label><button className="button secondary" onClick={saveInterviewAnswer} disabled={!interviewAnswer.trim()}>Save answer & next</button><button className="button primary" onClick={finishInterview} disabled={!interviewAnswers.length}>Finish session</button></div>{interviewAnswers.length > 0 && <p className="muted">{interviewAnswers.length} answer{interviewAnswers.length === 1 ? '' : 's'} saved in this session.</p>}</section><aside className="panel lab-aside"><span className="eyebrow light-eyebrow">YOUR PRACTICE HISTORY</span><h3>Make your examples concrete.</h3><p className="muted">Anchor each answer to a project, explain your contribution, and say how you measured the result. Review specific gaps in your Evidence Ledger before practicing.</p><div className="check-history"><span className="mini-score">{workspace.interview_sessions.length}</span><div><b>Sessions completed</b><small>Saved privately to your workspace</small></div></div></aside></div>}
  </>
}

const projectTemplate = (skill: string) => {
  const text = skill.toLowerCase()
  if (text.includes('docker')) return { title: 'Ship a production-ready container', brief: 'Package a small API as a hardened container. Document how another developer can build, run, and inspect it.', tasks: ['Create a minimal Dockerfile with a non-root runtime user', 'Add a health check and sensible environment configuration', 'Run it with Docker Compose and verify the service responds', 'Write setup instructions and capture a short demo'] }
  if (text.includes('git')) return { title: 'Build a reviewable open-source contribution', brief: 'Create a small repository with meaningful commits, an issue, a branch, and a pull-request-style change log.', tasks: ['Write a clear README and a focused starter issue', 'Create a feature branch with small, descriptive commits', 'Add tests and show the before/after behavior', 'Write a contribution note explaining decisions and review feedback'] }
  if (text.includes('test')) return { title: 'Create a tested service slice', brief: 'Build a small service with clear behavior, isolated dependencies, and a CI check that runs on each change.', tasks: ['Define the behavior contract and edge cases', 'Write fast unit tests using a controlled fake dependency', 'Add one integration test around the service boundary', 'Run the suite in CI and document what the tests do not cover'] }
  if (text.includes('sql') || text.includes('postgres') || text.includes('database')) return { title: 'Model and query a small data product', brief: 'Design a relational schema, expose a few useful queries, and explain how you preserve data integrity.', tasks: ['Sketch the schema and identify keys and constraints', 'Implement migrations and seed a realistic sample', 'Add tested queries and inspect a query plan', 'Document transaction boundaries and an indexing tradeoff'] }
  if (text.includes('react') || text.includes('frontend')) return { title: 'Build a polished, data-backed interface', brief: 'Create an accessible interface for one real workflow with loading, empty, error, and success states.', tasks: ['Define the user flow and accessible interaction states', 'Build reusable components and responsive layouts', 'Connect the interface to a typed data source', 'Add interaction tests and publish a short walkthrough'] }
  return { title: `Build a focused ${skill} portfolio project`, brief: `Create a small, complete product slice that demonstrates ${skill} through a working artifact and clear technical explanation.`, tasks: [`Choose a concrete problem that needs ${skill}`, 'Build a small end-to-end version with a clear user outcome', 'Add tests or verification steps for the main behavior', 'Publish a README with setup, design choices, and your contribution'] }
}

function PortfolioPage({ workspace, update, run }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null }) {
  const [artifactKind, setArtifactKind] = useState<'repository' | 'deployed_project' | 'certificate' | 'writeup' | 'other'>('repository')
  const [artifactTitle, setArtifactTitle] = useState('')
  const [artifactUrl, setArtifactUrl] = useState('')
  const [artifactDescription, setArtifactDescription] = useState('')
  const [artifactSkills, setArtifactSkills] = useState('')
  const [artifactChecks, setArtifactChecks] = useState({ goal_clear: false, setup_present: false, tests_present: false, ownership_clear: false, link_verified: false })
  const [error, setError] = useState('')
  const targets = run?.gaps.filter(gap => gap.verdict !== 'has').slice(0, 6) ?? []
  const saveArtifact = (event: React.FormEvent) => {
    event.preventDefault()
    if (!artifactTitle.trim()) { setError('Give your artifact a clear title.'); return }
    if (artifactUrl && !/^https?:\/\//i.test(artifactUrl)) { setError('Use a complete https:// or http:// link.'); return }
    const artifact = { id: makeId(), kind: artifactKind, title: artifactTitle.trim(), url: artifactUrl.trim(), description: artifactDescription.trim(), skill_ids: artifactSkills.split(',').map(item => item.trim()).filter(Boolean).slice(0, 30), added_at: now(), quality_checks: artifactChecks }
    update(current => ({ ...current, artifacts: [artifact, ...current.artifacts].slice(0, 100) }))
    setArtifactTitle(''); setArtifactUrl(''); setArtifactDescription(''); setArtifactSkills(''); setArtifactChecks({ goal_clear: false, setup_present: false, tests_present: false, ownership_clear: false, link_verified: false }); setError('')
  }
  const makeProject = (skill: string) => {
    const template = projectTemplate(skill)
    const tasks = template.tasks.map(label => ({ id: makeId(), label, completed: false }))
    update(current => ({ ...current, projects: [{ id: makeId(), title: template.title, brief: template.brief, skill_ids: [skill], tasks, created_at: now() }, ...current.projects].slice(0, 100) }))
  }
  const checks: Array<[keyof typeof artifactChecks, string]> = [['goal_clear', 'The project goal is clear'], ['setup_present', 'Setup instructions work'], ['tests_present', 'Tests or a demo show behavior'], ['ownership_clear', 'My contribution is explicit'], ['link_verified', 'I checked the link is public and works']]
  return <>
    <PageHeading kicker="PORTFOLIO STUDIO · 04" title="Turn a gap into something you can show." body="Build a small proof project for a priority skill, track its milestones, and connect finished artifacts to the skills they demonstrate." action={<span className="metric-chip">{workspace.projects.length} projects · {workspace.artifacts.length} artifacts</span>} />
    <section className="panel project-ideas"><div className="panel-title"><div><span className="eyebrow light-eyebrow">PROJECT STARTERS</span><h2>Pick a gap. Build proof.</h2></div><span className="count-badge">{targets.length} suggested</span></div>{targets.length ? <div className="project-idea-grid">{targets.map((gap, index) => { const idea = projectTemplate(gap.canonical_name); return <article className="project-idea" key={gap.skill_id} style={{ animationDelay: `${index * 65}ms` }}><span className="idea-topline">{gap.hard_requirement ? 'REQUIRED GAP' : 'PREFERRED GAP'} <i>·</i> Δ {gap.level_delta}</span><h3>{idea.title}</h3><p>{idea.brief}</p><div className="idea-skill">Demonstrates <b>{gap.canonical_name}</b></div><button className="button secondary" onClick={() => makeProject(gap.skill_id)}>Add project plan <span>↗</span></button></article> })}</div> : <div className="studio-empty compact"><span className="empty-orbit">✳</span><h3>Run an analysis to get project starters.</h3><p>Templates will be tailored to the highest-priority skills in your selected role.</p></div>}</section>
    <div className="portfolio-layout"><section className="panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">BUILD TRACKER</span><h2>Your project milestones</h2></div><span className="count-badge">{workspace.projects.length} active</span></div>{workspace.projects.length ? workspace.projects.map(project => { const done = project.tasks.filter(task => task.completed).length; return <article className="project-track" key={project.id}><div className="project-track-head"><div><h3>{project.title}</h3><p>{project.brief}</p></div><button className="icon-button" aria-label={`Remove ${project.title}`} onClick={() => update(current => ({ ...current, projects: current.projects.filter(item => item.id !== project.id) }))}>×</button></div><div className="project-progress"><span>{done}/{project.tasks.length} milestones</span><i><em style={{ width: `${project.tasks.length ? done / project.tasks.length * 100 : 0}%` }} /></i></div><div className="project-checklist">{project.tasks.map(task => <label key={task.id} className={task.completed ? 'checked' : ''}><input type="checkbox" checked={task.completed} onChange={event => update(current => ({ ...current, projects: current.projects.map(item => item.id === project.id ? { ...item, tasks: item.tasks.map(existing => existing.id === task.id ? { ...existing, completed: event.target.checked } : existing) } : item) }))} /><span />{task.label}</label>)}</div></article> }) : <div className="studio-empty compact"><h3>No project plans yet</h3><p>Add one from a skill gap above, then check off each artifact-producing milestone.</p></div>}</section>
      <section className="panel artifact-panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">PORTFOLIO EVIDENCE</span><h2>Attach a proof link</h2></div><span className="panel-index">02</span></div><form className="studio-form" onSubmit={saveArtifact}><label>Artifact type<select value={artifactKind} onChange={event => setArtifactKind(event.target.value as typeof artifactKind)}><option value="repository">GitHub repository</option><option value="deployed_project">Deployed project</option><option value="certificate">Certificate</option><option value="writeup">Technical write-up</option><option value="other">Other proof</option></select></label><label>Title<input value={artifactTitle} onChange={event => setArtifactTitle(event.target.value)} placeholder="API reliability project" maxLength={180} required /></label><label>Link<input value={artifactUrl} onChange={event => setArtifactUrl(event.target.value)} placeholder="https://github.com/you/project" maxLength={2048} /></label><label>What does it prove?<textarea rows={3} value={artifactDescription} onChange={event => setArtifactDescription(event.target.value)} placeholder="Explain your role, implementation, and outcome." maxLength={2000} /></label><label>Skills shown <small>comma-separated</small><input value={artifactSkills} onChange={event => setArtifactSkills(event.target.value)} placeholder="Docker, Python, testing" /></label><div className="artifact-review"><b>My review checklist</b>{checks.map(([key, label]) => <label key={key}><input type="checkbox" checked={artifactChecks[key]} onChange={event => setArtifactChecks(current => ({ ...current, [key]: event.target.checked }))} /><span />{label}</label>)}</div>{error && <div className="error-box">{error}</div>}<button className="button primary">Save portfolio artifact <span>↗</span></button></form>{workspace.artifacts.slice(0, 4).map(artifact => <div className="artifact-row" key={artifact.id}><span className="artifact-symbol">↗</span><div><b>{artifact.title}</b><small>{artifact.kind.replaceAll('_', ' ')} · {artifact.skill_ids.join(', ') || 'skills not tagged'}</small>{artifact.url && <a href={artifact.url} target="_blank" rel="noreferrer">Open link</a>}</div><button className="icon-button" aria-label={`Remove ${artifact.title}`} onClick={() => update(current => ({ ...current, artifacts: current.artifacts.filter(item => item.id !== artifact.id) }))}>×</button></div>)}</section></div>
  </>
}

function profileFacts(run: RunState | null) {
  const facts: Array<{ text: string; source: string }> = []
  for (const project of run?.profile?.projects ?? []) facts.push({ text: `${project.name}: ${project.description}`.slice(0, 300), source: `Project · ${project.name}` })
  for (const experience of run?.profile?.experiences ?? []) facts.push({ text: `${experience.title}${experience.organization ? ` at ${experience.organization}` : ''}: ${experience.description}`.slice(0, 300), source: `Experience · ${experience.title}` })
  for (const course of run?.profile?.courses ?? []) if (course.description) facts.push({ text: `${course.name}: ${course.description}`.slice(0, 300), source: `Course · ${course.name}` })
  return facts
}

function ApplicationKitPage({ workspace, update, run }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null }) {
  const [company, setCompany] = useState(run?.company || '')
  const [draft, setDraft] = useState('')
  const [copyState, setCopyState] = useState('')
  const facts = profileFacts(run)
  const target = run?.role || 'the role'
  const evidenceSkills = run?.gaps.filter(gap => gap.verdict === 'has').map(gap => gap.canonical_name).slice(0, 5) ?? []
  const activeGaps = run?.gaps.filter(gap => gap.verdict !== 'has').map(gap => gap.canonical_name).slice(0, 3) ?? []
  const bullets = facts.map(fact => `${fact.text} [${fact.source}]`).slice(0, 8)
  const talking = [
    ...facts.slice(0, 3).map(fact => `Prepare a specific example: ${fact.text}`),
    ...(activeGaps.length ? [`For ${activeGaps.join(', ')}, explain your current learning plan and what you can demonstrate today.`] : []),
  ].slice(0, 5)
  const createDraft = () => {
    const evidence = facts[0]?.text
    if (!evidence) { setCopyState('A resume-based analysis is needed to create evidence-backed application material.'); return }
    const skills = evidenceSkills.length ? `The record also contains evidence of ${evidenceSkills.join(', ')}.` : ''
    setDraft(`Dear ${company.trim() || 'Hiring Team'},\n\nI am applying for ${target}${company.trim() ? ` at ${company.trim()}` : ''}. My experience includes ${evidence}${skills ? ` ${skills}` : ''}\n\nI am also building the skills identified in my role analysis through a structured learning plan. I would welcome the opportunity to discuss the work in my portfolio and how it connects to this role.\n\nThank you for your consideration,\n${''}`)
    setCopyState('Draft built from source-backed profile facts. Review every sentence before using it.')
  }
  const savePack = () => {
    if (!draft.trim()) return
    update(current => ({ ...current, application_packs: [{ id: makeId(), role: target, company: company.trim(), resume_bullets: bullets, cover_letter: draft, talking_points: talking, created_at: now() }, ...current.application_packs].slice(0, 25) }))
    setCopyState('Application pack saved to your workspace.')
  }
  const copyDraft = async () => { try { await navigator.clipboard.writeText(draft); setCopyState('Draft copied to clipboard.') } catch { setCopyState('Clipboard access is unavailable here; select and copy the draft manually.') } }
  const downloadPack = () => { const text = `APPLICATION PACK · ${target}${company ? ` · ${company}` : ''}\n\nEVIDENCE-BACKED RESUME BULLETS\n${bullets.map(bullet => `• ${bullet}`).join('\n')}\n\nCOVER LETTER DRAFT\n${draft}\n\nINTERVIEW TALKING POINTS\n${talking.map(point => `• ${point}`).join('\n')}`; const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' })); link.download = 'placementgap-application-pack.txt'; link.click(); URL.revokeObjectURL(link.href) }
  return <>
    <PageHeading kicker="APPLICATION KIT · 05" title="Tell your story with proof behind it." body="Build a role-specific starter pack from the coursework, projects, and experience in your analyzed record. Every suggested bullet names its source." action={<span className="metric-chip">{facts.length} source-backed facts</span>} />
    {!facts.length && <div className="warning-box">Your latest run does not include parsed resume evidence. Upload a resume and analyze a role before generating application material.</div>}
    <div className="application-kit-grid"><section className="panel"><div className="panel-title"><div><span className="eyebrow light-eyebrow">ROLE CONTEXT</span><h2>Tailor your starter pack</h2></div><span className="panel-index">01</span></div><div className="studio-form"><label>Company<input value={company} onChange={event => setCompany(event.target.value)} placeholder="Company name" maxLength={120} /></label><div className="role-context-chip"><span>Target role</span><b>{target}</b></div><button className="button primary" onClick={createDraft} disabled={!facts.length}>Build evidence-backed draft <span>↗</span></button></div><div className="verified-facts"><span className="eyebrow light-eyebrow">FACTS FROM YOUR RECORD</span>{facts.length ? facts.map((fact, index) => <article key={`${fact.source}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><p>{fact.text}</p><small>{fact.source}</small></article>) : <p className="muted">Parsed resume facts appear here after a successful analysis.</p>}</div></section><section className="panel pack-preview"><div className="panel-title"><div><span className="eyebrow light-eyebrow">COVER LETTER STARTER</span><h2>Review and edit each line</h2></div><span className="pill">DRAFT</span></div><textarea className="pack-textarea" rows={14} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Generate a draft from your source-backed profile, then edit it in your own voice." maxLength={8000} /><div className="pack-actions"><button className="button secondary" disabled={!draft} onClick={() => void copyDraft()}>Copy draft</button><button className="button secondary" disabled={!draft} onClick={downloadPack}>Download pack</button><button className="button primary" disabled={!draft} onClick={savePack}>Save pack</button></div>{copyState && <div className="studio-note">{copyState}</div>}<div className="pack-subsections"><div><b>Resume bullet starters</b>{bullets.length ? bullets.map((bullet, index) => <p key={index}>“{bullet}”</p>) : <p className="muted">No source-backed bullets yet.</p>}</div><div><b>Interview talking points</b>{talking.map((point, index) => <p key={index}>{point}</p>)}</div></div></section></div>{workspace.application_packs.length > 0 && <section className="panel saved-packs"><span className="eyebrow light-eyebrow">SAVED DRAFTS</span><h3>Your application pack history</h3>{workspace.application_packs.slice(0, 5).map(pack => <button key={pack.id} onClick={() => { setCompany(pack.company); setDraft(pack.cover_letter); setCopyState(`Opened saved pack for ${pack.role}.`) }}><span>{pack.role}{pack.company ? ` · ${pack.company}` : ''}</span><small>{dateLabel(pack.created_at)}</small><b>Open ↗</b></button>)}</section>}
  </>
}

function ResourcesPage({ run }: { run: RunState | null }) {
  const [filter, setFilter] = useState('all')
  const resources = useMemo(() => {
    const unique = new Map<string, { skill: string; title: string; url: string; kind: string; cost: number; relevance: number; checked: string | null }>()
    for (const week of run?.plan?.weeks ?? []) for (const item of week.items) for (const resource of item.resources) {
      const existing = unique.get(resource.url)
      if (existing) { existing.skill += `, ${item.canonical_name}`; existing.relevance = Math.max(existing.relevance, resource.relevance) }
      else unique.set(resource.url, { skill: item.canonical_name, title: resource.title, url: resource.url, kind: resource.kind, cost: resource.estimated_cost_usd, relevance: resource.relevance, checked: resource.checked_at })
    }
    return [...unique.values()].sort((a, b) => (b.relevance - a.relevance) || (a.cost - b.cost))
  }, [run?.run_id])
  const shown = resources.filter(item => filter === 'all' || (filter === 'free' ? item.cost === 0 : item.kind.toLowerCase().includes(filter)))
  return <>
    <PageHeading kicker="LEARNING LIBRARY · 06" title="Resources attached to your plan." body="Explore sources selected for your scheduled skills. Ranking favors relevance and known cost; confirm availability and access terms on the source itself." action={<span className="metric-chip">{resources.length} unique resources</span>} />
    <section className="panel resource-panel"><div className="resource-filters">{[['all','All resources'],['free','No listed cost'],['documentation','Documentation'],['course','Courses'],['book','Books']].map(([key,label]) => <button key={key} className={filter === key ? 'selected' : ''} onClick={() => setFilter(key)}>{label}</button>)}</div>{shown.length ? <div className="resource-grid">{shown.map((resource,index) => <article className="resource-card" style={{animationDelay:`${index*40}ms`}} key={resource.url}><div className="resource-card-meta"><span>{resource.kind.toUpperCase()}</span><i>{resource.cost === 0 ? 'NO COST LISTED' : `$${resource.cost.toFixed(2)}`}</i></div><h3>{resource.title}</h3><p>For <b>{resource.skill}</b></p><div className="resource-quality"><span><i className="quality-dot" />{Math.round(resource.relevance*100)}% relevance score</span><span>{resource.checked ? `Listed ${resource.checked}` : 'Freshness unavailable'}</span></div><a className="button secondary" href={resource.url} target="_blank" rel="noreferrer">Open learning resource <span>↗</span></a></article>)}</div> : <div className="studio-empty compact"><span className="empty-orbit">✳</span><h3>{run ? 'No resources are attached to this plan yet.' : 'Build a plan to unlock your resources.'}</h3><p>Start an analysis with a full role description to get skill-specific learning links here.</p></div>}</section><p className="muted fine-print">Prices and links are shown as provided by the resource finder. “No cost listed” does not guarantee a source has no paid features.</p>
  </>
}

function MarketPage({ run }: { run: RunState | null }) {
  const [region, setRegion] = useState('')
  const skills = [...(run?.gaps ?? [])].sort((a,b) => b.market_demand_weight-a.market_demand_weight)
  const overall = skills.length ? Math.round(skills.reduce((sum, item) => sum + item.market_demand_weight, 0) / skills.length * 100) : 0
  return <>
    <PageHeading kicker="CAREER CONTEXT · 07" title="Understand what your role prioritizes." body="See how the selected role’s requirements are weighted in the bundled skill taxonomy, and which gaps carry the strongest signal for this target." action={<label className="market-region">Region<input value={region} onChange={event => setRegion(event.target.value)} placeholder="e.g. Bengaluru" maxLength={80} /></label>} />
    {!run && <RunEvidence run={run} />}
    {run && <><section className="market-summary"><div className="market-score"><small>ROLE REQUIREMENT WEIGHT</small><b>{overall}<i>/100</i></b><span>mean taxonomy demand weight</span></div><div className="market-explainer"><span className="eyebrow">{run.role || 'Selected role'}{region ? ` · ${region}` : ''}</span><h3>Put learning time where the role puts emphasis.</h3><p>Priority uses hard/ preferred classification, level delta, effort, prerequisite effects, and the ontology’s demand weight. The bars below show that demand input separately from your fit verdict.</p><span className="source-disclosure">SOURCE · BUNDLED PLACEMENTGAP SKILL TAXONOMY</span></div></section><div className="market-skill-list">{skills.map((gap,index) => <article className="market-skill" key={gap.skill_id}><span className="market-rank">{String(index+1).padStart(2,'0')}</span><div className="market-skill-name"><b>{gap.canonical_name}</b><small>{gap.hard_requirement ? 'Required' : 'Preferred'} · your verdict: <em className={`verdict ${gap.verdict}`}>{gap.verdict}</em></small></div><div className="market-bar"><i><em style={{width:`${Math.round(gap.market_demand_weight*100)}%`}} /></i><small>{Math.round(gap.market_demand_weight*100)} weight</small></div><span className="market-gap-delta">Δ {gap.level_delta}</span></article>)}</div><div className="market-disclaimer"><b>How to read this</b><p>This is a relative weighting bundled with PlacementGap’s skill taxonomy—not live vacancy counts, salary data, or a regional labor-market forecast. No external service is contacted when you enter a region.</p></div></>}
  </>
}

function ApplicationsPage({ workspace, update, run }: { workspace: WorkspaceData; update: (recipe: (current: WorkspaceData) => WorkspaceData) => void; run: RunState | null }) {
  const [company, setCompany] = useState('')
  const [role, setRole] = useState(run?.role ?? '')
  const [jobUrl, setJobUrl] = useState('')
  const [deadline, setDeadline] = useState('')
  const [error, setError] = useState('')
  const add = (event: React.FormEvent) => {
    event.preventDefault()
    if (!company.trim() || !role.trim()) { setError('Company and role are required.'); return }
    if (jobUrl && !/^https?:\/\//i.test(jobUrl)) { setError('Use a complete https:// or http:// job link.'); return }
    update(current => ({ ...current, applications: [{ id: makeId(), company: company.trim(), role: role.trim(), job_url: jobUrl.trim(), status: 'saved' as const, deadline, notes: '', run_id: run?.run_id ?? null, created_at: now() }, ...current.applications].slice(0, 100) }))
    setCompany(''); setRole(''); setJobUrl(''); setDeadline(''); setError('')
  }
  const lanes: Array<[WorkspaceData['applications'][number]['status'], string]> = [['saved','Saved'],['applied','Applied'],['screen','Screen'],['interview','Interview'],['offer','Offer'],['rejected','Closed']]
  return <>
    <PageHeading kicker="APPLICATION PIPELINE · 08" title="Keep your search in one place." body="Track roles from shortlist to outcome, save deadlines and notes, and keep the analysis that informed each application nearby." action={<span className="metric-chip">{workspace.applications.length} tracked</span>} />
    <section className="panel application-add"><div className="panel-title"><div><span className="eyebrow light-eyebrow">ADD TO YOUR PIPELINE</span><h2>Save an opportunity</h2></div><span className="panel-index">01</span></div><form className="application-form" onSubmit={add}><label>Company<input value={company} onChange={event => setCompany(event.target.value)} placeholder="Company name" required maxLength={120} /></label><label>Role<input value={role} onChange={event => setRole(event.target.value)} placeholder="Role title" required maxLength={120} /></label><label>Job link<input value={jobUrl} onChange={event => setJobUrl(event.target.value)} placeholder="https://..." maxLength={2048} /></label><label>Deadline<input type="date" value={deadline} onChange={event => setDeadline(event.target.value)} /></label><button className="button primary">Add role <span>↗</span></button></form>{error && <div className="error-box">{error}</div>}</section>
    <div className="application-summary">{lanes.slice(0,5).map(([status,label]) => <div key={status}><small>{label.toUpperCase()}</small><b>{workspace.applications.filter(item => item.status === status).length}</b></div>)}</div>
    <section className="pipeline-board">{lanes.map(([status,label]) => { const items=workspace.applications.filter(item=>item.status===status); return <div className="pipeline-lane" key={status}><div className="pipeline-lane-head"><span className={`pipeline-dot ${status}`} /><b>{label}</b><small>{items.length}</small></div>{items.map(item=><article className="application-card" key={item.id}><div className="application-card-top"><span>{item.company}</span><button className="icon-button" aria-label={`Remove ${item.role} at ${item.company}`} onClick={()=>update(current=>({...current,applications:current.applications.filter(existing=>existing.id!==item.id)}))}>×</button></div><h3>{item.role}</h3>{item.deadline && <small className="application-deadline">Deadline · {item.deadline}</small>}{item.job_url && <a href={item.job_url} target="_blank" rel="noreferrer">View job ↗</a>}{item.run_id && <small>Analysis · {item.run_id.slice(0,8)}</small>}<label className="status-select">Stage<select value={item.status} onChange={event=>update(current=>({...current,applications:current.applications.map(existing=>existing.id===item.id?{...existing,status:event.target.value as typeof existing.status}:existing)}))}>{lanes.map(([value,text])=><option value={value} key={value}>{text}</option>)}</select></label><label className="notes-label">Notes<textarea value={item.notes} onChange={event=>update(current=>({...current,applications:current.applications.map(existing=>existing.id===item.id?{...existing,notes:event.target.value}:existing)}))} rows={2} placeholder="Next step, contact, or reminder" maxLength={3000}/></label></article>)}</div> })}</section>
  </>
}
