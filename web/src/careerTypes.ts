export type GapSnapshot = {
  skill_id: string
  canonical_name: string
  verdict: 'has' | 'partial' | 'missing'
  level_delta: number
  priority_score: number
}

export type SavedRole = {
  id: string
  title: string
  company: string
  location: string
  url: string
  description: string
  run_id: string | null
  gaps: GapSnapshot[]
  created_at: string
}

export type WorkspaceData = {
  saved_roles: SavedRole[]
  roadmap: { completed_task_ids: string[]; minutes_by_task: Record<string, number> }
  skill_checks: Array<{
    id: string; skill_id: string; skill_name: string; correct: number; total: number
    confidence: number; completed_at: string
  }>
  projects: Array<{
    id: string; title: string; brief: string; skill_ids: string[]
    tasks: Array<{ id: string; label: string; completed: boolean }>; created_at: string
  }>
  artifacts: Array<{
    id: string; kind: 'repository' | 'deployed_project' | 'certificate' | 'writeup' | 'other'
    title: string; url: string; description: string; skill_ids: string[]; added_at: string
    quality_checks: { goal_clear: boolean; setup_present: boolean; tests_present: boolean; ownership_clear: boolean; link_verified: boolean }
  }>
  applications: Array<{
    id: string; company: string; role: string; job_url: string
    status: 'saved' | 'applied' | 'screen' | 'interview' | 'offer' | 'rejected'
    deadline: string; notes: string; run_id: string | null; created_at: string
  }>
  application_packs: Array<{
    id: string; role: string; company: string; resume_bullets: string[]
    cover_letter: string; talking_points: string[]; created_at: string
  }>
  interview_sessions: Array<{
    id: string; role: string
    answers: Array<{ prompt: string; answer: string; self_rating: number }>
    completed_at: string
  }>
}

export const emptyWorkspace: WorkspaceData = {
  saved_roles: [],
  roadmap: { completed_task_ids: [], minutes_by_task: {} },
  skill_checks: [],
  projects: [],
  artifacts: [],
  applications: [],
  application_packs: [],
  interview_sessions: [],
}

export type CareerTab = 'Roadmap' | 'Roles' | 'Skill Lab' | 'Portfolio' | 'Application Kit' | 'Resources' | 'Market' | 'Applications'

export const careerTabs: CareerTab[] = [
  'Roadmap', 'Roles', 'Skill Lab', 'Portfolio', 'Application Kit', 'Resources', 'Market', 'Applications',
]

export function completedTaskKey(runId: string, skillId: string): string {
  return `${runId}:${skillId}`
}
