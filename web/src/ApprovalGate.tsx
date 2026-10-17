import { useState } from 'react'

type Props = { runId: string; plan: any; onSubmitted: () => void }

export default function ApprovalGate({ runId, plan, onSubmitted }: Props) {
  const [note, setNote] = useState('')
  const [weeks, setWeeks] = useState(8)
  const [hours, setHours] = useState(8)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (decision: 'approve' | 'reject' | 'edit') => {
    setBusy(true); setError('')
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? ''}/runs/${runId}/approve`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, note, edits: decision === 'edit' ? { weeks, hours_per_week: hours } : {} }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail ?? 'Could not submit the review decision')
      onSubmitted()
    } catch (error) { setError(error instanceof Error ? error.message : 'Request failed') } finally { setBusy(false) }
  }
  return <section className="panel approval-panel">
    <div className="panel-title"><div><span className="eyebrow">HUMAN CHECKPOINT</span><h2>Review this plan</h2></div><span className="pill awaiting_approval">action required</span></div>
    <div className="review-summary"><span>{plan?.weeks?.length ?? 0} active weeks</span><span>{plan?.total_hours ?? 0} planned hours</span><span>{plan?.satisfied_skills?.length ?? 0} already met</span><span>{plan?.deferred?.length ?? 0} deferred</span></div>
    <div className="review-weeks">{(plan?.weeks ?? []).map((week: any) => {
      const sessions = (plan?.weeks ?? []).flatMap((row: any) => row.items ?? []).map((item: any) => ({
        item,
        hours: item.weekly_hours?.[week.week] ?? (item.week === week.week ? item.hours : 0),
      })).filter((session: any) => session.hours > 0)
      return <div className="review-week" key={week.week}><b>Week {week.week}</b><span>{week.scheduled_hours}/{week.capacity_hours}h</span><ul>{sessions.map(({ item, hours }: any) => <li key={item.skill_id}>{item.canonical_name} · {hours}h{item.week !== week.week ? ' continuation' : ''}</li>)}</ul></div>
    })}</div>
    <div className="edit-fields"><label>Plan horizon (weeks)<input type="number" min="1" max="104" value={weeks} onChange={event => setWeeks(Number(event.target.value))} /></label><label>Hours per week<input type="number" min="0.5" max="100" step="0.5" value={hours} onChange={event => setHours(Number(event.target.value))} /></label></div>
    <label className="field-label">Review note<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add context for an edit or rejection…" /></label>
    {error && <div className="error-box">{error}</div>}
    <div className="action-row"><button className="button ghost" disabled={busy} onClick={() => submit('reject')}>Reject with note</button><button className="button secondary" disabled={busy || (!note.trim())} onClick={() => submit('edit')}>Rebuild plan</button><button className="button primary" disabled={busy} onClick={() => submit('approve')}>Approve plan</button></div>
    <p className="muted small">Edits restart the deterministic solver and return to this review gate. Approval generates the Markdown, PDF, and JSON report.</p>
  </section>
}
