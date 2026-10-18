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
  directory_basis?: 'build_file' | 'unknown' | 'clone_destination'
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
  warnings?: string[]
  is_demo?: boolean
  is_saved?: boolean
}
