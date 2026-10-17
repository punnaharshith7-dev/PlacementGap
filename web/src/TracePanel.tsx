import { useState } from 'react'
import type { TraceRow } from './types'

export default function TracePanel({ traces }: { traces: TraceRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const groups = new Map<string, TraceRow[]>()
  for (const row of traces) groups.set(row.node_name, [...(groups.get(row.node_name) ?? []), row])
  return <section className="panel trace-panel">
    <div className="panel-title"><div><span className="eyebrow">OBSERVABILITY</span><h2>Node traces</h2></div><span className="count-badge">{traces.length} calls</span></div>
    {groups.size === 0 && <div className="empty-state">Trace rows will appear as each node completes.</div>}
    {[...groups.entries()].map(([node, rows]) => <div className="trace-group" key={node}>
      <button className="trace-head" onClick={() => setExpanded(expanded === node ? null : node)}>
        <span className="chevron">{expanded === node ? '⌄' : '›'}</span><strong>{node}</strong><span>{rows.length} rows</span>
      </button>
      {expanded === node && <div className="trace-body">{rows.map((row, index) => <div className="trace-card" key={`${node}-${index}`}>
        <div className="trace-stats"><span>{row.call_type}</span><span>{row.model}</span><span>{row.latency_ms} ms</span><span>{row.input_tokens}/{row.output_tokens} tokens</span><span>${row.cost_usd.toFixed(5)}</span><span>{row.retry_count} retries</span>{row.cache_hit && <em>cache hit</em>}</div>
        <div className="trace-version">prompt {row.prompt_version} · {new Date(row.timestamp).toLocaleTimeString()}</div>
        {Object.keys(row.metadata).length > 0 && <pre>{JSON.stringify(row.metadata, null, 2)}</pre>}
      </div>)}</div>}
    </div>)}
  </section>
}
