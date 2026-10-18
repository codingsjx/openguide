import type { Guide } from './guide'

export function parseSavedGuide(text: string): Guide {
  const data = JSON.parse(text)
  if (!data || !/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(data.repo_url ?? '') ||
      !Array.isArray(data.steps) || data.steps.length > 100 || typeof data.unsuitable !== 'boolean') {
    throw new Error('指南格式无效，需要 GitHub 仓库地址和 steps 列表')
  }
  const ids = new Set<number>()
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
    if (step.execution_record != null) {
      const record = step.execution_record
      if (!['passed', 'failed', 'timed_out'].includes(record.status) || record.command !== step.command ||
          record.commit_sha !== data.default_branch || !/^[0-9a-f]{40}$/.test(record.commit_sha) ||
          ['environment', 'summary', 'report'].some((field) => typeof record[field] !== 'string')) {
        throw new Error('执行记录与当前命令或固定提交不一致')
      }
    }
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
