import type { Guide, GuideStep } from './guide'

export type LearningStatus = 'pending' | 'done' | 'blocked' | 'skipped'
export interface LearningRecord { status: LearningStatus; note: string }
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
      stage_modes, requested_mode, model_timeout_s, stage_fallbacks, issue_discovery } = guide
    const warnings = (guide.warnings ?? []).filter((w) => !w.startsWith('已保存指南仅在本机展示'))
    const raw = JSON.stringify({ repo_url, owner, repo, default_branch, unsuitable, reasons, steps,
      generation_mode, stage_modes, requested_mode, model_timeout_s, stage_fallbacks, issue_discovery, warnings })
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
  }
  return lines.join('\n')
}
