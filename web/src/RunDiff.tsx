import { useState } from 'react'

const formatPlanItem = (item: any) => item
  ? `${item.hours}h total · ${Object.entries(item.weekly_hours ?? {}).map(([week, hours]) => `W${week} ${hours}h`).join(' + ') || `W${item.week}`}`
  : '—'

export default function RunDiff() {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [diff, setDiff] = useState<any>(null)
  const [error, setError] = useState('')
  const compare = async () => {
    setError(''); setDiff(null)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? ''}/runs/${encodeURIComponent(a)}/diff/${encodeURIComponent(b)}`, { credentials: 'include' })
      const value = await response.json()
      if (!response.ok) throw new Error(value.detail ?? 'Could not compare runs')
      setDiff(value)
    } catch (exception) { setError(exception instanceof Error ? exception.message : 'Request failed') }
  }
  return <section className="panel">
    <div className="panel-title"><div><span className="eyebrow">COMPARISON</span><h2>Run diff</h2></div></div>
    <div className="diff-controls"><input value={a} onChange={event => setA(event.target.value)} placeholder="Run A ID" /><span>↔</span><input value={b} onChange={event => setB(event.target.value)} placeholder="Run B ID" /><button className="button secondary" onClick={compare} disabled={!a || !b}>Compare</button></div>
    {error && <div className="error-box">{error}</div>}
    {diff && <div className="diff-grid"><div><h3>Gap verdict changes</h3>{Object.keys(diff.gap_verdicts).length ? Object.entries(diff.gap_verdicts).map(([key, value]: [string, any]) => <div className="diff-row" key={key}><b>{key}</b><span className="diff-old">{value.a ?? '—'}</span><span>→</span><span className="diff-new">{value.b ?? '—'}</span></div>) : <p className="muted">No verdict changes.</p>}</div><div><h3>Plan changes</h3>{Object.keys(diff.plan_items).length ? Object.entries(diff.plan_items).map(([key, value]: [string, any]) => <div className="diff-row" key={key}><b>{key}</b><span>{formatPlanItem(value.a)}</span><span>→</span><span>{formatPlanItem(value.b)}</span></div>) : <p className="muted">No scheduled item changes.</p>}</div></div>}
  </section>
}
