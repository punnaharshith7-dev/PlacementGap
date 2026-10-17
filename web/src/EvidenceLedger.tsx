import { useState } from 'react'
import type { RunState } from './types'

export default function EvidenceLedger({ run }: { run: RunState | null }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  if (!run) return <section className="panel evidence-ledger empty-state">Your evidence ledger appears here after an analysis.</section>

  return <section className="panel evidence-ledger">
    <div className="panel-title"><div><span className="eyebrow light-eyebrow">SOURCE-BACKED FINDINGS</span><h2>Evidence ledger</h2></div><span className="count-badge">{run.gaps.length} requirements</span></div>
    <p className="muted">Open a requirement to see what the job asks for, what your record supports, and the source passages used.</p>
    {!run.gaps.length && <div className="empty-state">No requirements were extracted. Add the complete job description and run the analysis again.</div>}
    <div className="ledger-list">{run.gaps.map(gap => {
      const open = expanded === gap.skill_id
      return <article className={`ledger-item ${open ? 'is-open' : ''}`} key={gap.skill_id}>
        <button className="ledger-head" onClick={() => setExpanded(open ? null : gap.skill_id)} aria-expanded={open}>
          <span className={`verdict-dot ${gap.verdict}`} /><span className="ledger-skill"><b>{gap.canonical_name}</b><small>{gap.hard_requirement ? 'Required' : 'Preferred'} · expects {gap.required_level.replaceAll('_', ' ')}</small></span>
          <span className={`verdict ${gap.verdict}`}>{gap.verdict}</span><span className="ledger-delta">Δ {gap.level_delta}</span><span className="ledger-toggle">{open ? '−' : '+'}</span>
        </button>
        {open && <div className="ledger-detail"><p>{gap.rationale}</p><div className="evidence-columns">
          <div><span className="eyebrow light-eyebrow">YOUR RECORD</span>{gap.evidence.length ? gap.evidence.map((item, index) => <blockquote className="source-quote" key={`${item.span.source_doc_id}-${item.span.char_start}-${index}`}><p>“{item.span.quote || item.explanation || 'Evidence passage available in source document.'}”</p><div><span>{item.evidence_type.replaceAll('_', ' ')}</span><span>{item.level.replaceAll('_', ' ')}</span><span>chars {item.span.char_start}–{item.span.char_end}</span><small>{Math.round(item.span.extractor_confidence * 100)}% extraction confidence</small></div></blockquote>) : <div className="no-evidence">No matching source passage was found in the supplied record.</div>}</div>
          <div className="requirement-source"><span className="eyebrow light-eyebrow">JOB DESCRIPTION</span><div className="source-quote"><p>Requirement: {gap.canonical_name} · {gap.hard_requirement ? 'required' : 'preferred'} · {gap.required_level.replaceAll('_', ' ')}</p><small>Priority score {gap.priority_score.toFixed(2)} · demand weight {gap.market_demand_weight.toFixed(2)}</small></div></div>
        </div></div>}
      </article>
    })}</div>
  </section>
}
