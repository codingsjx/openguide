import type { Guide, GuideStep } from './guide'

export type LearningStatus = 'pending' | 'done' | 'blocked' | 'skipped'
export type ExecutionStatus = 'unrecorded' | 'not_run' | 'passed' | 'failed' | 'timed_out'
export interface LearningExecution {
  status: ExecutionStatus; command: string; directory: string; exitCode: string; scope: string; summary: string
}
export interface LearningRecord { status: LearningStatus; note: string; execution?: LearningExecution }
export const executionLabels: Record<ExecutionStatus, string> = {
  unrecorded: '尚未记录执行情况', not_run: '未运行', passed: '自行记录通过', failed: '失败', timed_out: '超时',
}
export const emptyExecution = (): LearningExecution => ({ status: 'unrecorded', command: '', directory: '', exitCode: '', scope: '', summary: '' })
export function updateLearningRecord(record: LearningRecord | undefined, patch: Partial<LearningRecord>): LearningRecord {
  return { status: 'pending', note: '', ...record, ...patch }
}
export function executionProblems(execution?: LearningExecution): string[] {
  if (!execution) return []
  const problems: string[] = []
  if (execution.exitCode.trim() && !/^-?\d{1,10}$/.test(execution.exitCode.trim())) problems.push('退出码应填写整数；未取得时留空。')
  if (execution.status === 'not_run' && execution.exitCode.trim()) problems.push('“未运行”与已填退出码不一致，请核对实际情况。')
  if (execution.status === 'passed') {
    if (!execution.command.trim() || !execution.directory.trim() || !execution.scope.trim() || !execution.summary.trim()) problems.push('记录通过前，请补齐实际命令、实际目录、运行范围和结果摘要。')
    if (execution.exitCode.trim() !== '0') problems.push('记录通过时请核对退出码为 0；失败或超时应如实记录。')
  }
  return problems
}
export interface LearningProgress { identity: string; currentStepId: number; records: Record<string, LearningRecord> }
export interface ProgressStorage { getItem(key: string): string | null; setItem(key: string, value: string): void }
const LAST_GUIDE_KEY = 'openguide.learning.last-guide.v1'

export const learningLabels: Record<LearningStatus, string> = {
  pending: '未记录完成', done: '已自行核对', blocked: '卡住了', skipped: '暂缓',
}
export const phaseGoals = {
  A: '准备可用的本地开发环境，分别核对各组件的版本、工具和依赖。',
  B: '取得真实的检查结果，区分测试、构建、失败、跳过与未运行项。',
  C: '确定一个范围明确的任务，记录问题来源、复现方式和验收方法。',
  D: '整理实际改动、验证记录和待审阅草稿，再核对仓库的提交要求。',
}

// Exact identity comparison prevents carrying completion into a new revision
// or a regenerated workflow. The compact hash is only a storage key.
export function learningIdentity(guide: Guide): string {
  return JSON.stringify([guide.repo_url.replace(/\/$/, '').toLowerCase(), guide.default_branch, Boolean(guide.is_demo),
    guide.steps.map((s) => [s.step_id, s.stage, s.title, s.command, s.working_directory ?? null,
      s.evidence.kind, s.evidence.source, s.evidence.quote, s.evidence.verification ?? 'missing',
      s.evidence.line_start ?? null, s.evidence.line_end ?? null, s.directory_basis ?? 'unknown', s.prerequisite_step_ids ?? [],
      s.required_paths ?? [], s.missing_inputs ?? [], s.expected, s.success_checks ?? []])])
}

export function progressKey(identity: string): string {
  let a = 2166136261, b = 5381
  for (let i = 0; i < identity.length; i++) {
    const c = identity.charCodeAt(i)
    a = Math.imul(a ^ c, 16777619); b = Math.imul(b, 33) ^ c
  }
  return `openguide.learning.v1.${(a >>> 0).toString(36)}.${(b >>> 0).toString(36)}`
}

export function emptyLearningProgress(guide: Guide): LearningProgress {
  return { identity: learningIdentity(guide), currentStepId: guide.steps[0]?.step_id ?? 0, records: {} }
}

export function loadLearningProgress(guide: Guide, storage: ProgressStorage): LearningProgress {
  const empty = emptyLearningProgress(guide)
  try {
    const raw = storage.getItem(progressKey(empty.identity))
    if (!raw || raw.length > 500_000) return empty
    const data = JSON.parse(raw)
    if (!data || data.identity !== empty.identity || !data.records || typeof data.records !== 'object' || Array.isArray(data.records)) return empty
    const ids = new Set(guide.steps.map((s) => String(s.step_id)))
    const records: Record<string, LearningRecord> = {}
    for (const [id, record] of Object.entries(data.records)) {
      const r = record as LearningRecord
      if (!ids.has(id) || !r || !['pending', 'done', 'blocked', 'skipped'].includes(r.status) || typeof r.note !== 'string' || r.note.length > 1000) return empty
      records[id] = { status: r.status, note: r.note }
      if (r.execution !== undefined) {
        const e = r.execution
        // Ignore a damaged extension without discarding legacy notes/progress.
        if (e && typeof e.status === 'string' && Object.hasOwn(executionLabels, e.status) &&
          ['command', 'directory', 'exitCode', 'scope', 'summary'].every((field) => typeof e[field as keyof LearningExecution] === 'string' && e[field as keyof LearningExecution].length <= (field === 'exitCode' ? 20 : 1000))) {
          records[id].execution = { status: e.status, command: e.command, directory: e.directory, exitCode: e.exitCode, scope: e.scope, summary: e.summary }
        }
      }
    }
    return { ...empty, records, currentStepId: ids.has(String(data.currentStepId)) ? Number(data.currentStepId) : empty.currentStepId }
  } catch { return empty }
}

export function saveLearningProgress(progress: LearningProgress, storage: ProgressStorage): boolean {
  try {
    const raw = JSON.stringify(progress)
    if (raw.length > 500_000) return false
    storage.setItem(progressKey(progress.identity), raw)
    return true
  } catch { return false }
}

export function rememberLearningGuide(guide: Guide, storage: ProgressStorage): boolean {
  if (guide.is_demo) return true
  try {
    // Store the guide only. Follow-up logs, question history and settings are
    // separate component state and never enter this snapshot.
    const { repo_url, owner, repo, default_branch, unsuitable, reasons, steps, generation_mode,
      stage_modes, requested_mode, model_timeout_s, stage_fallbacks, issue_discovery, model_request_attempts, model_disconnect_retries,
      generation_strategy, model_service_retries } = guide
    const warnings = (guide.warnings ?? []).filter((w) => !w.startsWith('已保存指南仅在本机展示'))
    const raw = JSON.stringify({ repo_url, owner, repo, default_branch, unsuitable, reasons, steps,
      generation_mode, stage_modes, requested_mode, model_timeout_s, stage_fallbacks, issue_discovery, model_request_attempts, model_disconnect_retries,
      generation_strategy, model_service_retries, warnings })
    if (raw.length > 2_000_000) return false
    if (storage.getItem(LAST_GUIDE_KEY) !== raw) storage.setItem(LAST_GUIDE_KEY, raw)
    return true
  } catch { return false }
}

export function lastLearningGuide(storage: ProgressStorage): string | null {
  try {
    const raw = storage.getItem(LAST_GUIDE_KEY)
    return raw && raw.length <= 2_000_000 ? raw : null
  } catch { return null }
}

export function pendingPrerequisites(guide: Guide, step: GuideStep, progress: LearningProgress): GuideStep[] {
  const records = progress.identity === learningIdentity(guide) ? progress.records : {}
  return (step.prerequisite_step_ids ?? []).flatMap((id) => {
    const prerequisite = guide.steps.find((s) => s.step_id === id)
    return prerequisite && records[String(id)]?.status !== 'done' ? [prerequisite] : []
  })
}

export function nextLearningAction(step: GuideStep, progress: LearningProgress, prerequisites: GuideStep[], canAsk = true): string {
  if (progress.records[String(step.step_id)]?.status === 'blocked') return canAsk
    ? '先记录卡点，再展开“报错了”粘贴脱敏日志排查。尚未解决时可以暂缓，后续从步骤目录返回。'
    : '先记录卡点并打开固定版本出处核对；当前为本机查看，联网重新生成后可继续使用报错帮助。'
  if (prerequisites.length) return `先核对第 ${prerequisites.map((s) => s.step_id).join('、')} 步的准备情况；已有环境时也应核对适用范围。浏览后续步骤不会标记完成。`
  if (step.missing_inputs?.length) return '先核对缺失路径、目录和版本，再执行命令。路径尚未确认时，保留待处理状态。'
  if (step.command && step.directory_basis !== 'clone_destination' && !step.working_directory) return canAsk
    ? '先从出处确认执行目录，再复制命令。确认不清楚时使用“这步太粗”或保留卡点。'
    : '先从出处确认执行目录，再复制命令。确认不清楚时保留卡点，联网重新生成后继续追问。'
  if (step.evidence.kind === 'missing') return '先补齐本步的原文要求。通用帮助可用于准备，不能替代仓库专属规范；未确认时可以暂缓。'
  return '按本步核对目标操作，把实际结果记在下面；只有自己核对完成后，再记录完成并继续。'
}

const escape = (value: string) => Array.from(value).map((c) => '\\`*_{}[]()<>#!'.includes(c) ? '\\' + c : c).join('')
export function learningMarkdown(guide: Guide, progress: LearningProgress): string {
  const matches = progress.identity === learningIdentity(guide)
  const records = matches ? progress.records : {}
  const completed = guide.steps.filter((s) => records[String(s.step_id)]?.status === 'done').length
  const lines = ['# OpenGuide 学习记录', '', `仓库：${guide.repo_url}`, `指南资料版本：${escape(guide.default_branch)}`,
    `手动记录完成：${completed}/${guide.steps.length}`, '', '所有状态及摘要均由使用者自行记录，未经独立核验；系统没有执行命令，不代表测试通过、PR 已提交或贡献已被接受。', '']
  for (const step of guide.steps) {
    const record = records[String(step.step_id)]
    lines.push(`## 第 ${step.step_id} 步 · ${escape(step.title)}`, `阶段：${step.stage}；状态：${learningLabels[record?.status ?? 'pending']}`, '')
    if (step.command) lines.push('指南操作（未由工具执行）：', ...step.command.split('\n').map((line) => '    ' + line), '',
      `指南建议目录：${escape(step.directory_basis === 'clone_destination' ? '自行选择的项目存放目录' : step.working_directory || '尚未确认')}`, '')
    lines.push(`来源：${escape(step.evidence.kind === 'missing' ? '待核对' : step.evidence.source)}`,
      `本步摘要：${record?.note.trim() ? escape(record.note) : '未填写'}`, '')
    const e = record?.execution
    if (e) {
      lines.push('### 使用者填写的执行记录（未经核验）', `执行情况：${executionLabels[e.status]}`,
        `实际命令：${e.command.trim() ? escape(e.command) : '未填写'}`, `实际目录：${e.directory.trim() ? escape(e.directory) : '未填写'}`,
        `退出码：${e.exitCode.trim() ? escape(e.exitCode) : '未取得'}`, `运行范围：${e.scope.trim() ? escape(e.scope) : '未填写'}`,
        `结果、失败与跳过项摘要：${e.summary.trim() ? escape(e.summary) : '未填写'}`,
        ...executionProblems(e).map((problem) => `待核对：${problem}`), '')
    }
  }
  return lines.join('\n')
}
