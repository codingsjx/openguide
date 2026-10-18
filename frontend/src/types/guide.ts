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
