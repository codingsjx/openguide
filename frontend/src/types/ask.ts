export interface AskSource {
  id: string
  kind: 'file' | 'issue' | 'tree'
  source: string
  quote: string
  url: string
  line_start: number | null
  line_end: number | null
  verification: 'literal_quote' | 'tree_entry'
  intents: string[]
  note: string
}

export interface AskResult {
  repo_url: string
  question: string
  resolved_question: string
  context_used: boolean
  revision: string
  intents: string[]
  status: 'answered' | 'insufficient_evidence' | 'unavailable'
  mode: 'ai' | 'extractive' | 'no_evidence'
  fallback_reason: string
  verification_issue: string
  points: { text: string; citations: string[] }[]
  commands: { command: string; citation: string; working_directory: string | null; directory_basis: string }[]
  sources: AskSource[]
  missing: string[]
  next_actions: string[]
  warnings: string[]
  links: { label: string; url: string }[]
}

export interface AskTurn { id: number; question: string; result: AskResult }

function canonicalRepo(value: string): string {
  return value.trim().replace(/^https?:\/\/(?:www\.)?github\.com\//i, '').replace(/\/$/, '').replace(/\.git$/, '').toLowerCase()
}

export function questionsForRequest(turns: AskTurn[], repo: string): string[] {
  return turns.filter((t) => canonicalRepo(t.result.repo_url) === canonicalRepo(repo)).slice(-4).map((t) => t.question)
}

export function safeSourceHref(result: AskResult, source: AskSource): string | undefined {
  try {
    const url = new URL(source.url)
    const base = new URL(result.repo_url)
    if (url.origin !== 'https://github.com' || url.username || url.password || base.origin !== url.origin) return undefined
    const path = base.pathname.replace(/\/$/, '')
    if (source.kind === 'issue') {
      const prefix = path + '/issues/'
      return url.pathname.startsWith(prefix) && /^[1-9]\d*$/.test(url.pathname.slice(prefix.length)) ? url.href : undefined
    }
    return url.pathname.startsWith(path + '/blob/' + encodeURIComponent(result.revision) + '/') ? url.href : undefined
  } catch { return undefined }
}

const escape = (text: string) => Array.from(text).map((c) => '\\`*_{}[]()<>#!'.includes(c) ? '\\' + c : c).join('')

export function conversationMarkdown(turns: AskTurn[]): string {
  const lines = ['# OpenGuide 仓库问答记录', '', '原文匹配不代表 AI 解读已独立复核，也不代表执行过命令。', '']
  for (const turn of turns) {
    const r = turn.result
    lines.push(`## 问题 ${turn.id}：${escape(turn.question)}`, '', `仓库：${r.repo_url}`, `参考提交：${r.revision || '未取得'}`, `回答方式：${r.mode === 'ai' ? 'AI 解读（引用已匹配原文）' : r.mode === 'extractive' ? '原文整理' : '资料不足'}`, '')
    for (const p of r.points) lines.push(escape(p.text) + ' [' + p.citations.join(', ') + ']', '')
    for (const c of r.commands) lines.push('原文操作入口（未执行） [' + c.citation + ']：', '```text', c.command, '```', '')
    if (r.missing.length) lines.push('仍缺资料：', ...r.missing.map((s) => '- ' + escape(s)), '')
    lines.push('下一步（通用建议）：', ...r.next_actions.map((s) => '- ' + escape(s)), '', '出处：')
    for (const source of r.sources) {
      const href = safeSourceHref(r, source)
      lines.push(href ? `- [${source.id} ${escape(source.source)}](${href})` : '- ' + escape(source.source))
    }
    if (r.warnings.length) lines.push('', '采集及生成说明：', ...r.warnings.map((s) => '- ' + escape(s)))
    lines.push('')
  }
  return lines.join('\n')
}
