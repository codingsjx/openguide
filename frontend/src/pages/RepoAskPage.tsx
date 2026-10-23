import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Input, Space, Switch, Tag, Typography } from 'antd'
import { api } from '../api/client'
import { conversationMarkdown, questionsForRequest, safeSourceHref, type AskTurn } from '../types/ask'
import { GuideNotices } from '../components/GuideStatus'
import { fallbackLabels } from '../types/guideStatus'

const { Title, Paragraph, Text } = Typography
const examples = ['开发环境怎么安装？', '测试应该怎么运行？', '提交 PR 有哪些要求？', '代码目录和入口在哪里？']

function AnswerCard({ turn }: { turn: AskTurn }) {
  const top = useRef<HTMLDivElement>(null)
  useEffect(() => { top.current?.scrollIntoView({ behavior:'smooth', block:'start' }) }, [])
  const r = turn.result
  const modelNotes = r.warnings.filter((w) => /问答模型|问答生成模型/.test(w))
  const sourceById = (id: string) => r.sources.find((s) => s.id === id)
  return <div ref={top}><Card style={{ marginTop: 16 }} title={`问题 ${turn.id}`}>
    <Paragraph strong>{turn.question}</Paragraph>
    <Tag color={r.mode === 'ai' ? 'blue' : r.mode === 'no_evidence' ? 'orange' : 'default'}>{r.mode === 'ai' ? 'AI 解读 · 引用已匹配原文' : r.mode === 'extractive' ? '原文整理' : '资料不足'}</Tag>
    {r.fallback_reason && <Text type="secondary">{r.fallback_reason === 'answer_unverified' ? 'AI 解读未通过原文核验' : fallbackLabels[r.fallback_reason] || '本轮未获得可用 AI 解读'}</Text>}
    {r.context_used && <details style={{ marginTop: 8 }}><summary>已承接前文 · 查看本轮理解</summary><Paragraph style={{ whiteSpace: 'pre-wrap' }}>{r.resolved_question}</Paragraph></details>}
    {modelNotes.map((w) => <Paragraph type="secondary" key={w} style={{ marginTop: 8 }}>{w}</Paragraph>)}
    {r.points.map((point, i) => <Paragraph key={i} style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}>
      {point.text}{' '}{point.citations.map((id) => {
        const source = sourceById(id)
        const href = source && safeSourceHref(r, source)
        return href ? <a key={id} href={href} target="_blank" rel="noreferrer">[{id}] 原文 </a> : <Text key={id}>[{id}] </Text>
      })}
    </Paragraph>)}
    {r.missing.length > 0 && <Alert style={{ marginTop: 12 }} showIcon type="warning" message={r.status === 'unavailable' ? '暂时无法取得仓库资料' : '这些信息仍需补充'} description={<ul>{r.missing.map((text) => <li key={text}>{text}</li>)}</ul>} />}
    {r.commands.length > 0 && <div style={{ marginTop: 14 }}>
      <Text strong>原文操作入口（尚未执行）</Text>
      <Paragraph type="secondary">先核对工作目录、前置条件和运行范围，原文匹配不代表已在本机通过。</Paragraph>
      {r.commands.map((c, i) => <div key={i} style={{ marginTop: 8 }}>
        <Paragraph copyable={{ text: c.command }} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><Text code>{c.command}</Text> [{c.citation}]</Paragraph>
        <Paragraph type="secondary">{c.directory_basis === 'clone_destination' ? '执行位置：你选择的项目存放目录，克隆后再进入仓库。' : c.working_directory ? `执行位置（${c.directory_basis === 'document_context' ? '由原文上下文推导' : '由构建文件推导'}）：${c.working_directory === '.' ? '仓库根目录' : c.working_directory}` : '执行目录尚未确认，请核对原文。'}</Paragraph>
      </div>)}
    </div>}
    <div style={{ marginTop: 14 }}><Text strong>下一步（通用建议）</Text><ul>{r.next_actions.map((text) => <li key={text}>{text}</li>)}</ul><Space wrap>{r.links.map((link) => <a key={link.url} href={link.url} target="_blank" rel="noreferrer">{link.label}</a>)}</Space></div>
    <div style={{ marginTop: 14 }}><Text strong>原文与出处</Text>
      <Paragraph type="secondary">可查看完整片段及固定版本原文；引用匹配只核验文字来源，AI 解读仍需结合上下文判断。</Paragraph>
      {r.sources.map((source, i) => <details key={source.id} open={r.points.length ? source.id === r.points[0].citations[0] : i === 0} style={{ marginTop: 10 }}>
        <summary style={{ cursor: 'pointer', overflowWrap: 'anywhere' }}>[{source.id}] {source.source}{source.line_start ? ` · L${source.line_start}–L${source.line_end}` : ''}{source.kind === 'tree' ? ' · 仅确认路径存在' : ''}</summary>
        {safeSourceHref(r, source) && <a href={safeSourceHref(r, source)} target="_blank" rel="noreferrer">打开原始出处 ↗</a>}
        {source.note && <Paragraph type="secondary" style={{ marginTop: 6 }}>{source.note}</Paragraph>}
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', background: '#f6f8fa', padding: 10, borderRadius: 6 }}>{source.quote}</pre>
      </details>)}
    </div>
    <div style={{ marginTop: 16 }}><GuideNotices guide={{ repo_url:r.repo_url,owner:'',repo:'',default_branch:r.revision || '未取得',unsuitable:false,reasons:[],steps:[] }} warnings={r.warnings.filter((w) => !modelNotes.includes(w))} /></div>
  </Card></div>
}

export default function RepoAskPage({ initialUrl }: { initialUrl: string }) {
  const [url, setUrl] = useState(initialUrl)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<AskTurn[]>([])
  const [revision, setRevision] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const [useAi, setUseAi] = useState(true)
  const active = useRef<AbortController | null>(null)
  const initialRef = useRef(initialUrl)

  function reset() {
    active.current?.abort(); active.current = null
    setLoading(false); setTurns([]); setRevision(undefined); setError(''); setQuestion('')
  }
  useEffect(() => {
    if (initialUrl && initialUrl !== initialRef.current) {
      initialRef.current = initialUrl
      reset(); setUrl(initialUrl)
    }
  }, [initialUrl])
  useEffect(() => () => { active.current?.abort(); active.current = null }, [])
  useEffect(() => {
    if (!loading) return
    const start = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [loading])

  async function ask(value = question) {
    const text = value.trim(); const repo = url.trim()
    if (!text || !repo || loading) return
    const controller = new AbortController()
    active.current = controller
    setQuestion(text); setLoading(true); setElapsed(0); setError('')
    try {
      const result = await api.postAsk({ url:repo, question:text, history:questionsForRequest(turns,repo), revision, use_llm:useAi }, controller.signal)
      if (active.current !== controller) return
      setTurns((old) => [...old, { id:(old.at(-1)?.id ?? 0)+1,question:text,result }])
      if (/^[0-9a-f]{40}$/.test(result.revision)) setRevision(result.revision)
      setQuestion('')
    } catch (e) {
      if (active.current === controller) setError(e instanceof Error ? e.message : '问答失败，请重试')
    } finally {
      if (active.current === controller) { active.current = null; setLoading(false) }
    }
  }

  function download() {
    const href=URL.createObjectURL(new Blob([conversationMarkdown(turns)],{type:'text/markdown;charset=utf-8'}))
    const a=document.createElement('a'); a.href=href; a.download='OpenGuide-仓库问答记录.md'; a.click(); URL.revokeObjectURL(href)
  }

  return <div className="ask-page">
    <div className="section-heading"><span className="section-kicker">REPOSITORY Q&A</span>
    <Title level={3}>仓库贡献问答</Title>
    <Paragraph type="secondary">围绕当前仓库提问或追问，先看回答，再核对原文。资料不足时会说明缺什么。</Paragraph>
    </div>
    <Card>
      <label><Text strong>当前仓库</Text><Input aria-label="问答仓库" value={url} maxLength={500} onChange={(e) => { reset(); setUrl(e.target.value) }} placeholder="GitHub 仓库地址" /></label>
      <Space wrap style={{ marginTop: 12 }}><Switch checked={useAi} onChange={setUseAi} disabled={loading} checkedChildren="AI 整理" unCheckedChildren="仅原文" /><Button onClick={reset} disabled={!turns.length && !loading && !question.trim() && !error}>开始新对话</Button><Button onClick={download} disabled={!turns.length}>下载问答记录</Button></Space>
      <Paragraph type="secondary" style={{ marginTop: 10, marginBottom: 0 }}>问题和检索片段可能交给当前配置的模型服务，请勿输入密钥或个人信息。上下文仅保留在本页，切换仓库会清空；追问沿用同一文件版本。</Paragraph>
    </Card>
    {!turns.length && <Space wrap style={{ marginTop: 12 }}>{examples.map((text) => <Button key={text} disabled={loading} onClick={() => ask(text)}>{text}</Button>)}</Space>}
    {turns.map((turn) => <AnswerCard key={turn.id} turn={turn} />)}
    <Card style={{ marginTop: 16 }}>
      <label><Text strong>{turns.length ? '继续追问' : '你的问题'}</Text><Input.TextArea aria-label="贡献问答问题" rows={3} maxLength={2000} showCount disabled={loading} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="例如：测试怎么运行？也可以接着问：这条命令在哪里执行？" /></label>
      <Space wrap style={{ marginTop: 14 }}><Button type="primary" disabled={!url.trim() || !question.trim()} loading={loading} onClick={() => ask()}>发送问题</Button>{loading && <Button onClick={() => { active.current?.abort(); active.current=null; setLoading(false); setError('已停止等待，后台可能仍在处理；你可以重试。') }}>取消等待</Button>}</Space>
      {loading && <Paragraph type="secondary" style={{ marginTop: 8 }}>正在核对仓库资料并整理回答，已等待 {elapsed} 秒。</Paragraph>}
      {error && <Alert showIcon type="error" style={{ marginTop: 12 }} message="本轮未完成" description={error} action={<Button size="small" onClick={() => ask()}>重试当前问题</Button>} />}
    </Card>
  </div>
}
