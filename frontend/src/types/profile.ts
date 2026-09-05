// Mirror of backend `Profile` schema (core/profile/schema.py).
// Keep in sync when A changes the schema.

export interface BuildInfo {
  tool: string | null
  package_manager: string | null
  test_cmd: string | null
  has_makefile: boolean
  has_dockerfile: boolean
}

export interface GfiInfo {
  count: number
  oldest_days: number | null
}

export interface ActivityInfo {
  commits_30d: number
  last_release_days: number | null
}

export type Suitability = 'promising' | 'unclear' | 'avoid'

export interface Profile {
  owner: string
  repo: string
  html_url: string
  description: string
  stars: number
  forks: number
  open_issues: number
  languages: Record<string, number>
  license: string | null
  default_branch: string
  has_readme: boolean
  has_contributing: boolean
  has_docs: boolean
  build: BuildInfo
  gfi: GfiInfo
  activity: ActivityInfo
  suitability: Suitability
  reasons: string[]
}
