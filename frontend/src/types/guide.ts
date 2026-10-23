// Mirror of backend GuideStep/Evidence (core/generate/schemas.py).

export interface Evidence {
  kind: 'file' | 'issue' | 'missing'
  source: string
  quote: string
  verification?: 'missing' | 'source_exists' | 'quote_verified' | 'command_verified'
  line_start?: number | null
  line_end?: number | null
  reason?: string
}

export interface GuideStep {
  step_id: number
  stage: 'A' | 'B' | 'C' | 'D'
  stage_label: string
  title: string
  command: string | null
  original_command?: string | null
  command_derivation?: string
  original_stage?: 'A' | 'B' | 'C' | 'D' | null
  working_directory?: string | null
  directory_basis?: 'build_file' | 'document_context' | 'unknown' | 'clone_destination'
  required_paths?: string[]
  missing_inputs?: string[]
  prerequisite_step_ids?: number[]
  context_notes?: string[]
  success_checks?: string[]
  execution_record?: {
    status: 'passed' | 'failed' | 'timed_out'
    command: string
    commit_sha: string
    environment: string
    summary: string
    report: string
    working_directory?: string | null
  } | null
  expected: string
  fail_hints: string[]
  evidence: Evidence
}

export interface Guide {
  repo_url: string
  owner: string
  repo: string
  default_branch: string
  unsuitable: boolean
  reasons: string[]
  steps: GuideStep[]
  generation_mode?: 'heuristic' | 'llm' | 'mixed'
  stage_modes?: Partial<Record<'A' | 'B' | 'C' | 'D', 'heuristic' | 'llm'>>
  requested_mode?: 'ai' | 'rules' | 'unknown'
  model_timeout_s?: number | null
  stage_fallbacks?: Partial<Record<'A' | 'B' | 'C' | 'D', 'not_configured' | 'model_timeout' | 'model_auth_failed' | 'model_rate_limited' | 'model_error' | 'invalid_output' | 'evidence_unverified' | 'incomplete_workflow' | 'no_stage_evidence'>>
  warnings?: string[]
  is_demo?: boolean
  is_saved?: boolean
  issue_discovery?: {
    status: 'candidates' | 'untriaged' | 'empty' | 'unavailable' | 'blocked'
    reason: string
    sampled_at: string
    sampled_count: number
    blocked_count: number
    candidates: { number: number; title: string; url: string; labels: string[]; checks: string[]; origin: 'labelled' | 'untriaged' }[]
    search_links: { label: string; url: string }[]
  } | null
}
