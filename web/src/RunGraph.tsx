const nodes = ['intake', 'jd_discovery', 'jd_extract', 'profile_parse', 'profile_normalize', 'gap_analysis', 'prioritize', 'plan_build', 'critic', 'human_approval', 'report']

export default function RunGraph({ events, status }: { events: Array<{ type: string; data: Record<string, unknown> }>; status: string }) {
  const latest = new Map<string, Record<string, unknown>>()
  for (const event of events) {
    const node = String(event.data.node ?? '')
    if (node) latest.set(node, event.data)
  }
  const branches = [nodes.slice(0, 3), nodes.slice(3, 5)]
  const entries = [...branches[0], ...branches[1], ...nodes.slice(5)]
  return <section className="panel graph-panel">
    <div className="panel-title"><div><span className="eyebrow">EXECUTION</span><h2>Run graph</h2></div><span className={`pill ${status}`}>{status.replaceAll('_', ' ')}</span></div>
    <div className="graph-flow">
      {entries.map((name, index) => {
        const event = latest.get(name)
        const done = Boolean(event)
        const active = !done && status === 'running' && index === Math.min(entries.length - 1, events.filter(item => item.type === 'node_end').length)
        return <div className={`graph-node ${done ? 'done' : ''} ${active ? 'active' : ''} ${name === 'human_approval' && status === 'awaiting_approval' ? 'waiting' : ''}`} key={name}>
          <span className="node-index">{String(index + 1).padStart(2, '0')}</span>
          <strong>{name.replaceAll('_', ' ')}</strong>
          <span className="node-meta">{done ? `${Number(event?.latency_ms ?? 0)} ms · $${Number(event?.cost_usd ?? 0).toFixed(4)}` : name === 'human_approval' && status === 'awaiting_approval' ? 'review required' : active ? 'executing' : 'queued'}</span>
        </div>
      })}
    </div>
    <div className="graph-legend"><span><i className="dot done-dot" /> complete</span><span><i className="dot active-dot" /> running</span><span><i className="dot wait-dot" /> approval</span></div>
  </section>
}
