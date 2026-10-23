import type { Guide } from './guide'

export interface ContributionInput {
  task: string
  issueUrl: string
  problem: string
  changeSummary: string
  baseRevision: string
  files: string
  patch: string
  testStatus: 'not_run' | 'passed' | 'failed'
  testCommand: string
  testExitCode: string
  testOutput: string
}

export const emptyContribution = (): ContributionInput => ({ task: '', issueUrl: '', problem: '', changeSummary: '', baseRevision: '', files: '', patch: '', testStatus: 'not_run', testCommand: '', testExitCode: '', testOutput: '' })

export interface ContributionPreparation { input: ContributionInput; referenceRevision: string }
const PREPARATION_FORMAT = 'openguide.contribution-preparation.v1'
const validPreparationRevision = (value: unknown): value is string => typeof value === 'string' && Boolean(value.trim()) && value.length <= 200
  && !Array.from(value).some((c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127)
const repositoryKey = (value: unknown): string | null => typeof value === 'string' && /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(value)
  ? value.replace(/\/$/, '').toLowerCase() : null

function preparationInput(value: unknown): ContributionInput {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('准备记录缺少有效表单')
  const input = emptyContribution()
  const raw = value as Record<string, unknown>
  for (const key of Object.keys(input) as (keyof ContributionInput)[]) {
    const field = Object.prototype.hasOwnProperty.call(raw, key) ? raw[key] : input[key]
    const limit = key === 'patch' ? 1_000_000 : ['task', 'issueUrl', 'baseRevision', 'testCommand', 'testExitCode'].includes(key) ? 1000 : 10000
    if (typeof field !== 'string' || field.length > limit) throw new Error('准备记录字段格式或长度无效')
    if (key === 'testStatus') {
      if (!['not_run', 'passed', 'failed'].includes(field)) throw new Error('准备记录测试状态无效')
      input.testStatus = field as ContributionInput['testStatus']
    } else input[key] = field
  }
  return input
}

export function contributionPreparationJson(guide: Guide, input: ContributionInput, referenceRevision = guide.default_branch): string {
  if (!validPreparationRevision(referenceRevision)) throw new Error('准备记录参考版本无效')
  const raw = JSON.stringify({ format: PREPARATION_FORMAT, repo_url: guide.repo_url,
    reference_revision: referenceRevision, input: preparationInput(input) }, null, 2)
  if (new TextEncoder().encode(raw).length > 2_000_000) throw new Error('准备记录超过 2 MB，请减少 diff 或测试输出后再导出')
  return raw
}

export function parseContributionPreparation(text: string, guide: Guide): ContributionPreparation {
  if (new TextEncoder().encode(text).length > 2_000_000) throw new Error('准备记录不能超过 2 MB')
  let data
  try { data = JSON.parse(text) } catch { throw new Error('准备记录不是有效 JSON') }
  if (!data || data.format !== PREPARATION_FORMAT) throw new Error('这不是贡献准备记录；指南 JSON 请在首页导入')
  if (!repositoryKey(data.repo_url) || repositoryKey(data.repo_url) !== repositoryKey(guide.repo_url)) throw new Error('准备记录属于其他仓库，不能覆盖当前仓库的表单')
  if (!validPreparationRevision(data.reference_revision)) throw new Error('准备记录参考版本无效')
  return { input: preparationInput(data.input), referenceRevision: data.reference_revision }
}

export function issueNumber(repoUrl: string, value: string): number | null {
  try {
    const url = new URL(value)
    const base = new URL(repoUrl)
    if (url.origin !== base.origin || url.username || url.password) return null
    const prefix = base.pathname.replace(/\/$/, '') + '/issues/'
    if (!url.pathname.startsWith(prefix)) return null
    const number = url.pathname.slice(prefix.length)
    return /^[1-9]\d*$/.test(number) && Number.isSafeInteger(Number(number)) ? Number(number) : null
  } catch { return null }
}

export function changedFiles(input: ContributionInput): string[] {
  const paths = input.patch.trim()
    ? [...input.patch.matchAll(/^diff --git a\/(.+) b\/(.+)\r?$/gm)].flatMap((m) => [m[1], m[2]])
    : input.files.split(/\r?\n/)
  return [...new Set(paths.map((p) => p.trim()).filter(Boolean))]
}

const safePath = (p: string) => p.length <= 500 && !/^(?:\/|[A-Za-z]:)/.test(p) && !p.includes('\\') && !p.split('/').some((s) => !s || s === '..' || s === '.') && ![...p].some((c) => c.charCodeAt(0) < 32)

export function contributionProblems(guide: Guide, input: ContributionInput): string[] {
  const errors: string[] = []
  if (!input.task.trim() || !input.problem.trim()) errors.push('请写明选定任务及其需要解决的问题。')
  if (input.issueUrl.trim() && issueNumber(guide.repo_url, input.issueUrl.trim()) === null) errors.push('任务链接必须是当前仓库的具体 issue 地址。')
  if (!input.changeSummary.trim()) errors.push('请描述已经做出的修改，尚未修改时先停留在任务准备阶段。')
  if (input.baseRevision.trim() && !/^[0-9a-f]{40}$/i.test(input.baseRevision.trim())) errors.push('改动基准提交须为完整的 40 位 Git 提交 SHA；无法确定时留空并在提交前核对。')
  const files = changedFiles(input)
  if (!files.length) errors.push('请填写实际修改的仓库相对路径，或粘贴标准 git diff 输出。')
  if (files.some((p) => !safePath(p))) errors.push('修改文件必须使用仓库相对路径，不能包含上级目录或绝对路径。')
  if (input.patch.length > 1_000_000) errors.push('diff 超过 1 MB，请只保留本次贡献需要的修改。')
  if (input.patch.trim() && (!/^diff --git /m.test(input.patch) || !/^(?:@@ |new file mode |deleted file mode |rename from )/m.test(input.patch))) errors.push('diff 缺少变更内容；请粘贴 git diff 或 git diff --cached 的实际输出。')
  if (input.testStatus !== 'not_run') {
    if (!input.testCommand.trim() || !input.testOutput.trim() || !/^-?\d+$/.test(input.testExitCode.trim())) errors.push('已执行测试时，请填写实际命令、退出码及结果摘要。')
    else if ((input.testStatus === 'passed') !== (Number(input.testExitCode) === 0)) errors.push('测试状态与退出码不一致：通过须退出 0，失败须为非零。')
  }
  return errors
}

export function buildContributionDraft(guide: Guide, input: ContributionInput, preparationRevision = guide.default_branch): string {
  const errors = contributionProblems(guide, input)
  if (errors.length) throw new Error(errors.join('\n'))
  const number = input.issueUrl.trim() ? issueNumber(guide.repo_url, input.issueUrl.trim()) : null
  const source = number ? `${guide.repo_url}/issues/${number}` : '人工选题；尚未关联 issue，请先确认维护者是否接受。'
  const files = changedFiles(input)
  const test = input.testStatus === 'not_run' ? '未运行测试，不能视为已验证。' : `${input.testStatus === 'passed' ? '用户记录为通过（未经工具执行验证）' : '测试失败，仍待处理'}\n\n实际命令：${input.testCommand.trim()}\n退出码：${input.testExitCode.trim()}\n结果摘要：${input.testOutput.trim()}`
  const sources = [...new Set(guide.steps.filter((s) => s.stage === 'D' && s.evidence.kind === 'file' && s.evidence.source).map((s) => {
    const [path, anchor] = s.evidence.source.split('#')
    return `${guide.repo_url}/blob/${encodeURIComponent(guide.default_branch)}/${path.split('/').map(encodeURIComponent).join('/')}${anchor ? '#' + anchor : ''}`
  }))]
  return `# PR 草稿：${input.task.trim().replace(/[\r\n]+/g, ' ')}

状态：待人工审阅，未提交。
由 OpenGuide 在本机按用户填写的任务、修改和测试记录整理；内容及来源未独立核验，不代表测试已执行、贡献已完成或维护者已接受。请按仓库政策披露实际 AI 协助范围。

## 任务来源
仓库：${guide.repo_url}
指南参考资料提交：${guide.default_branch}
${preparationRevision !== guide.default_branch ? `准备记录最初参考版本（用户文件，未独立核验）：${preparationRevision}\n准备记录与当前指南版本不同，贡献规范及验证要求仍需重新核对。\n` : ''}
用户记录的改动基准：${input.baseRevision.trim() || '未提供；提交前需核对。'}
${input.baseRevision.trim() && input.baseRevision.trim() !== guide.default_branch ? '改动基准与指南参考资料版本不同，请重新核对贡献规范及验证要求。\n' : ''}
${source}

## 问题与范围
${input.problem.trim()}

## 实际修改（用户提供）
${input.changeSummary.trim()}

修改文件：
${files.map((p) => '- ' + p).join('\n')}
路径依据：${input.patch.trim() ? '从用户粘贴的 diff 解析，未验证该 diff 对应本机工作区或参考提交。' : '用户手工填写，未核对工作区。'}

## 验证记录
${test}

## 仓库规范入口
${sources.length ? sources.map((s) => '- ' + s).join('\n') : '未取得贡献规范，请先查看仓库最新说明。'}

## 提交前检查
- [ ] 确认任务仍需处理、没有重复 PR，且符合维护者参与规则
- [ ] 核对分支、实际 diff 与本草稿内容一致
- [ ] 处理失败或未运行项，按仓库要求记录验证范围和限制
- [ ] 补充仓库 PR 模板所需内容及实际 AI 协助披露
- [ ] 人工审阅后再决定是否向上游提交
`
}
