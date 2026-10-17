export type TraceRow = {
  run_id: string
  node_name: string
  call_type: string
  model: string
  prompt_version: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  latency_ms: number
  retry_count: number
  cache_hit: boolean
  timestamp: string
  metadata: Record<string, unknown>
}

export type RunState = {
  run_id: string
  student_id: string
  role: string
  jd_url?: string | null
  company?: string | null
  status: string
  discovery_tier: string
  degraded: boolean
  degraded_reasons: string[]
  weeks: number
  hours_per_week: number
  gaps: Array<{ skill_id: string; canonical_name: string; verdict: 'has' | 'partial' | 'missing'; level_delta: number; priority_score: number; rationale: string; required_level: string; demonstrated_level: string; hard_requirement: boolean; market_demand_weight: number; prerequisite_ids: string[]; evidence: Evidence[] }>
  profile?: {
    source_doc_id: string
    raw_text: string
    evidence: Evidence[]
    courses: Array<{ name: string; description: string; grade?: string | null; skills: string[]; span: SourceSpan }>
    projects: Array<{ name: string; description: string; artifacts: string[]; skills: string[]; span: SourceSpan }>
    experiences: Array<{ title: string; organization: string; description: string; skills: string[]; span: SourceSpan }>
    demonstrated_skills: Record<string, string>
  } | null
  job?: { role: string; company?: string | null; text: string } | null
  plan?: { weeks: Array<{ week: number; capacity_hours: number; scheduled_hours: number; items: Array<{ skill_id: string; canonical_name: string; hours: number; weekly_hours: Record<number, number>; outcome: string; prerequisite_ids: string[]; resources: Array<{ title: string; url: string; kind: string; estimated_cost_usd: number; checked_at: string | null; relevance: number }> }> }>; deferred: Array<{ skill_id: string; canonical_name: string; reason: string; estimated_hours: number }>; satisfied_skills: string[]; total_hours: number; total_budget_hours: number; violations: string[] } | null
  report_markdown?: string | null
  report_json?: Record<string, unknown> | null
}

export type SourceSpan = { source_doc_id: string; char_start: number; char_end: number; extractor_confidence: number; quote: string }
export type Evidence = { skill_id: string; level: string; span: SourceSpan; evidence_type: string; explanation: string }

export type RunEvent = { id: number; type: string; data: Record<string, unknown>; created_at: string }
