import type { Guide } from './guide'

export function parseSavedGuide(text: string): Guide {
  const data = JSON.parse(text)
  if (!data || !/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(data.repo_url ?? '') ||
      !Array.isArray(data.steps) || data.steps.length > 100 || typeof data.unsuitable !== 'boolean') {
    throw new Error('指南格式无效，需要 GitHub 仓库地址和 steps 列表')
  }
  const ids = new Set<number>()
  if (data.stage_modes != null && (typeof data.stage_modes !== 'object' || Array.isArray(data.stage_modes) ||
      Object.entries(data.stage_modes).some(([stage, mode]) => !['A', 'B', 'C', 'D'].includes(stage) || !['heuristic', 'llm'].includes(mode as string)))) {
    throw new Error('阶段生成来源格式无效')
  }
  const relativePath = (value: unknown) => typeof value === 'string' && value.length > 0 && !/^(?:\/|[A-Za-z]:)/.test(value) && !value.includes('\\') && !value.split('/').includes('..')
  if (data.issue_discovery != null) {
    const d = data.issue_discovery
    const base = data.repo_url.replace(/\/$/, '')
    const strings = (value: unknown) => Array.isArray(value) && value.every((s: unknown) => typeof s === 'string')
    const searchUrl = (value: unknown) => {
      try {
        const u = new URL(value as string)
        return u.origin === 'https://github.com' && !u.username && !u.password && u.pathname === new URL(base).pathname + '/issues'
      } catch { return false }
    }
    if (!['candidates', 'untriaged', 'empty', 'unavailable', 'blocked'].includes(d.status) || typeof d.reason !== 'string' ||
        typeof d.sampled_at !== 'string' || ![d.sampled_count, d.blocked_count].every((n) => Number.isInteger(n) && n >= 0) ||
        !Array.isArray(d.candidates) || d.candidates.length > 3 || d.candidates.some((c: Record<string, unknown>) => !c ||
          !Number.isSafeInteger(c.number) || Number(c.number) <= 0 || typeof c.title !== 'string' || c.url !== `${base}/issues/${c.number}` ||
          !['labelled', 'untriaged'].includes(c.origin as string) || !strings(c.labels) || !strings(c.checks)) ||
        !Array.isArray(d.search_links) || d.search_links.length > 10 || d.search_links.some((l: Record<string, unknown>) => !l || typeof l.label !== 'string' || !searchUrl(l.url))) {
      throw new Error('任务候选或检索入口格式无效，链接必须属于当前仓库')
    }
  }
  for (const step of data.steps) {
    if (!step || !Number.isInteger(step.step_id) || ids.has(step.step_id) ||
        !['A', 'B', 'C', 'D'].includes(step.stage) || typeof step.title !== 'string' ||
        (step.expected != null && typeof step.expected !== 'string') ||
        (step.stage_label != null && typeof step.stage_label !== 'string') ||
        (step.command != null && typeof step.command !== 'string') ||
        (step.original_command != null && typeof step.original_command !== 'string') ||
        (step.command_derivation != null && typeof step.command_derivation !== 'string') ||
        !step.evidence || !['file', 'issue', 'missing'].includes(step.evidence.kind) ||
        typeof step.evidence.source !== 'string' || typeof step.evidence.quote !== 'string' ||
        (step.fail_hints != null && (!Array.isArray(step.fail_hints) || step.fail_hints.some((h: unknown) => typeof h !== 'string')))) {
      throw new Error('指南步骤或证据字段格式无效')
    }
    ids.add(step.step_id)
    if ((step.working_directory != null && !relativePath(step.working_directory)) ||
        (step.directory_basis != null && !['build_file', 'unknown', 'clone_destination'].includes(step.directory_basis)) ||
        ['required_paths', 'missing_inputs'].some((field) => step[field] != null && (!Array.isArray(step[field]) || step[field].some((p: unknown) => !relativePath(p)))) ||
        (step.context_notes != null && (!Array.isArray(step.context_notes) || step.context_notes.some((n: unknown) => typeof n !== 'string'))) ||
        (step.success_checks != null && (!Array.isArray(step.success_checks) || step.success_checks.some((n: unknown) => typeof n !== 'string'))) ||
        (step.prerequisite_step_ids != null && (!Array.isArray(step.prerequisite_step_ids) || step.prerequisite_step_ids.some((id: unknown) => !Number.isInteger(id))))) {
      throw new Error('操作目录或前置条件格式无效')
    }
    if (step.execution_record != null) {
      const record = step.execution_record
      if (!['passed', 'failed', 'timed_out'].includes(record.status) || record.command !== step.command ||
          record.commit_sha !== data.default_branch || !/^[0-9a-f]{40}$/.test(record.commit_sha) ||
          (record.working_directory != null && (!relativePath(record.working_directory) || record.working_directory !== step.working_directory)) ||
          ['environment', 'summary', 'report'].some((field) => typeof record[field] !== 'string')) {
        throw new Error('执行记录与当前命令或固定提交不一致')
      }
    }
  }
  const earlier = new Set<number>()
  for (const step of data.steps) {
    if ((step.prerequisite_step_ids ?? []).some((id: number) => !earlier.has(id))) throw new Error('前置步骤必须引用指南中已出现的步骤')
    earlier.add(step.step_id)
  }
  const [, owner, repo] = data.repo_url.match(/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+)\/?$/)
  return { ...data, owner, repo,
    default_branch: typeof data.default_branch === 'string' ? data.default_branch : 'main',
    reasons: Array.isArray(data.reasons) ? data.reasons.filter((r: unknown) => typeof r === 'string') : [],
    steps: data.steps.map((s: Guide['steps'][number]) => ({ ...s, expected: s.expected ?? '', stage_label: s.stage_label ?? '', fail_hints: s.fail_hints ?? [] })),
    is_saved: true, is_demo: false, warnings: ['已保存指南仅在本机展示，本次没有重新联网核验或执行命令；附带的历史执行记录未经独立核验。', ...(Array.isArray(data.warnings) ? data.warnings.filter((w: unknown) => typeof w === 'string') : [])] }
}

export function downloadGuide(guide: Guide) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(guide, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `OpenGuide-${guide.owner || 'saved'}-${guide.repo || 'guide'}.json`
  link.click()
  URL.revokeObjectURL(url)
}
