import { useEffect, useState } from 'react'

type EvalPayload = Record<string, any>

export default function EvalDashboard() {
  const [data, setData] = useState<EvalPayload | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { fetch(`${import.meta.env.VITE_API_URL ?? ''}/evals/latest`, { credentials: 'include' }).then(async response => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? 'No eval report'); setData(payload) }).catch(value => setError(value.message)) }, [])
  if (error) return <section className="panel"><div className="panel-title"><div><span className="eyebrow">EVALUATION</span><h2>Eval dashboard</h2></div></div><div className="empty-state">{error}. Run <code>make eval</code> to generate the dev report.</div></section>
  if (!data) return <section className="panel"><div className="empty-state">Loading evaluation metrics…</div></section>
  const metrics = data.metrics ?? {}
  const e2e = metrics.end_to_end ?? {}
  const component = metrics.component ?? {}
  const ops = metrics.ops ?? {}
  const ablations = data.ablations ?? []
  return <section className="eval-stack">
    <div className="panel"><div className="panel-title"><div><span className="eyebrow">FROZEN EVAL</span><h2>Evaluation dashboard</h2></div><span className="count-badge">{data.split} · {data.case_count} cases</span></div>
      <div className="metric-grid"><Metric label="Plan validity" value={formatPercent(e2e.plan_validity?.pass_rate)} /><Metric label="Task success" value={formatPercent(e2e.task_success_rate)} /><Metric label="Groundedness" value={formatPercent(e2e.groundedness)} /><Metric label="Cost p50" value={formatUsd(ops.cost_usd?.p50)} /><Metric label="Latency p95" value={formatMs(ops.latency_ms?.p95)} /><Metric label="Unresolved skills" value={formatPercent(component.canonicalization?.unresolved_rate)} /></div>
    </div>
    <div className="dashboard-grid"><div className="panel"><h3>Gap confusion matrix</h3><Confusion matrix={component.gap_classification?.confusion_matrix} /></div><div className="panel"><h3>Cost by node</h3><BarChart data={ops.cost_by_node ?? {}} formatter={formatUsd} /></div><div className="panel"><h3>Latency waterfall</h3><BarChart data={ops.latency_by_node_ms ?? {}} formatter={formatMs} /></div><div className="panel"><h3>Chaos recovery</h3><BarChart data={metrics.trajectory?.recovery_by_failure_type ?? {}} formatter={formatPercent} /></div></div>
    <div className="panel"><h3>Ablation results</h3>{ablations.length ? <div className="table-wrap"><table><thead><tr><th>Variant</th><th>Success</th><th>Validity</th><th>Cost / run</th><th>p95 latency</th></tr></thead><tbody>{ablations.map((item: any) => <tr key={item.variant}><td>{item.variant}</td><td>{formatPercent(item.success_rate)}</td><td>{formatPercent(item.plan_validity)}</td><td>{formatUsd(item.cost_per_run)}</td><td>{formatMs(item.p95_latency_ms)}</td></tr>)}</tbody></table></div> : <p className="muted">Run <code>make ablate</code> to populate the comparison table.</p>}</div>
  </section>
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric-card"><span>{label}</span><b>{value}</b></div> }
function formatPercent(value: unknown) { return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—' }
function formatUsd(value: unknown) { return typeof value === 'number' ? `$${value.toFixed(4)}` : '—' }
function formatMs(value: unknown) { return typeof value === 'number' ? `${Math.round(value)} ms` : '—' }
function Confusion({ matrix }: { matrix?: Record<string, Record<string, number>> }) {
  if (!matrix) return <p className="muted">No matrix in this report.</p>
  const labels = ['has', 'partial', 'missing']
  return <div className="matrix"><div className="matrix-head">gold ↓ / predicted →</div>{labels.map(row => <div className="matrix-row" key={row}><span>{row}</span>{labels.map(column => { const value = matrix[row]?.[column] ?? 0; return <b key={column} style={{ opacity: 0.2 + Math.min(0.8, value / 10) }}>{value}</b> })}</div>)}</div>
}
function BarChart({ data, formatter }: { data: Record<string, number>; formatter: (value: unknown) => string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, 10)
  const max = Math.max(1, ...entries.map(([, value]) => value))
  return <div className="bar-chart">{entries.length ? entries.map(([name, value]) => <div className="bar-row" key={name}><span>{name.replaceAll('_', ' ')}</span><div className="bar-track"><i style={{ width: `${Math.max(2, value / max * 100)}%` }} /></div><b>{formatter(value)}</b></div>) : <span className="muted">No data</span>}</div>
}
