import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Button,
  Card,
  Alert,
  Empty,
  Input,
  Space,
  Steps,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  FileTextOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  ZoomInOutlined,
  QuestionCircleOutlined,
  BugOutlined,
  RightOutlined,
  LeftOutlined,
} from '@ant-design/icons'

import { api, type FollowupResult } from '../../api/client'
import type { Evidence, Guide, GuideStep } from '../../types/guide'
import ContributionWorkbench from '../ContributionWorkbench'
import GuideStatus, { GuideNotices } from '../GuideStatus'
import GuideEntryHelp from '../GuideEntryHelp'
import { downloadGuide } from '../../types/savedGuide'
import LearningOverview from '../LearningOverview'
import { emptyExecution, executionLabels, executionProblems, updateLearningRecord, emptyLearningProgress, learningIdentity, learningLabels, learningMarkdown, loadLearningProgress, nextLearningAction, pendingPrerequisites, rememberLearningGuide, saveLearningProgress, type LearningExecution, type LearningProgress, type LearningStatus } from '../../types/learningProgress'

const { Paragraph, Text, Title } = Typography

const STAGE_META: Record<string, { color: string; label: string }> = {
  A: { color: 'blue', label: '环境搭建' },
  B: { color: 'purple', label: '测试基线' },
  C: { color: 'green', label: '挑选 issue' },
  D: { color: 'orange', label: '首次 PR 路径' },
}

// ---- Evidence badge + link ------------------------------------------------

function evidenceHref(guide: Guide, ev: Evidence): string | null {
  if (ev.kind === 'issue' && /^#?\d+$/.test(ev.source)) {
    const n = ev.source.replace('#', '')
    return `${guide.repo_url}/issues/${n}`
  }
  if (ev.kind === 'file' && ev.source) {
    const [path, line] = ev.source.split('#')
    return `${guide.repo_url}/blob/${guide.default_branch ?? 'main'}/${path.split('/').map(encodeURIComponent).join('/')}${
      line ? `#${line}` : ev.line_start ? `#L${ev.line_start}${ev.line_end && ev.line_end !== ev.line_start ? `-L${ev.line_end}` : ''}` : ''
    }`
  }
  return null
}

function EvidenceBadge({ guide, ev }: { guide: Guide; ev: Evidence }) {
  if (ev.kind === 'missing') {
    return (
      <Tag color="red" icon={<WarningOutlined />}>
        无来源标注
      </Tag>
    )
  }
  const href = evidenceHref(guide, ev)
  if (!href) {
    return (
      <Tag color="cyan" icon={<FileTextOutlined />}>
        {ev.source || '来源'}
      </Tag>
    )
  }
  return (
    <a href={href} target="_blank" rel="noreferrer">
      <Tag
        color={ev.kind === 'issue' ? 'green' : 'cyan'}
        icon={ev.kind === 'issue' ? <LinkOutlined /> : <FileTextOutlined />}
      >
        {ev.kind === 'issue' ? `issue ${ev.source}` : ev.source}
      </Tag>
    </a>
  )
}

// ---- Follow-up bar --------------------------------------------------------

function FollowupBar({
  step,
  url,
  guide,
  logOpen,
  onBlocked,
  onToggleLog,
}: {
  step: GuideStep
  url: string
  guide: Guide
  logOpen: boolean
  onBlocked: () => void
  onToggleLog: () => void
}) {
  const [logText, setLogText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [result, setResult] = useState<FollowupResult | null>(null)

  async function run(intent: 'granular' | 'explain' | 'diagnose') {
    if (busy) return
    if (intent === 'diagnose' && !logText.trim()) {
      void message.warning('先粘贴报错日志')
      return
    }
    setBusy(intent)
    setResult(null)
    try {
      const r = await api.postFollowup({
        url,
        intent,
        step: { ...step },
        revision: /^[0-9a-f]{40}$/.test(guide.default_branch) ? guide.default_branch : undefined,
        log_text: intent === 'diagnose' ? logText : '',
      })
      setResult(r)
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '追问失败')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <Space wrap size={6}>
        <Button size="small" disabled={!!busy} icon={<ZoomInOutlined />} loading={busy === 'granular'} onClick={() => run('granular')}>
          这步太粗
        </Button>
        <Button size="small" disabled={!!busy} icon={<QuestionCircleOutlined />} loading={busy === 'explain'} onClick={() => run('explain')}>
          看不懂为什么
        </Button>
        <Button size="small" disabled={!!busy} icon={<BugOutlined />} loading={busy === 'diagnose'} onClick={() => { if (!logOpen) onBlocked(); else onToggleLog() }}>
          报错了
        </Button>
      </Space>

      {logOpen && (
        <div style={{ marginTop: 8 }}>
          <Paragraph type="secondary">日志可能交给当前配置的模型服务分析；粘贴前请移除密钥、账号及个人信息。原始日志不会保存到学习记录，离开此步会清空。</Paragraph>
          <Input.TextArea
            autoFocus
            aria-label="脱敏报错日志"
            rows={3}
            value={logText}
            onChange={(e) => setLogText(e.target.value)}
            placeholder="把报错日志贴在这里…"
          />
          <Button
            size="small"
            type="primary"
            style={{ marginTop: 6 }}
            loading={busy === 'diagnose'}
            disabled={!!busy}
            onClick={() => run('diagnose')}
          >
            定位问题
          </Button>
        </div>
      )}

      {result && (
        <Card size="small" style={{ marginTop: 8, background: '#fafafa' }}>
          <Text strong>{result.intent === 'granular' ? '更细的步骤' : result.intent === 'explain' ? '为什么' : '定位'}</Text>
          <Paragraph style={{ marginTop: 6, whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {result.text}
          </Paragraph>
          <Paragraph type="secondary" style={{ marginTop: 8 }}>原文匹配只证明出处存在，不代表已确认根因或执行过命令。{result.mode === 'rules' ? '本次使用本地规则与检索。' : result.mode === 'llm_evidence_selection' ? '本次由 AI 选择原文，再逐字核验。' : '本次展示已核验的检索原文。'}</Paragraph>
          {result.explanations?.map((item) => <div key={item.label} style={{ marginTop: 12 }}>
            <Text strong>{item.label}</Text>
            <Paragraph style={{ marginTop: 4 }}>{item.text}</Paragraph>
            {item.reference_url && <a href={item.reference_url} target="_blank" rel="noreferrer">工具官方说明 ↗</a>}
          </div>)}
          {Boolean(result.preparation_checks?.length) && <div style={{ marginTop: 12 }}>
            <Text strong>{result.intent === 'granular' ? '1. 开始前核对（工具提供）' : '开始前核对（工具提供）'}</Text>
            <ol>{result.preparation_checks!.map((item) => <li key={item}>{item}</li>)}</ol>
          </div>}
          {result.sub_steps.length > 0 && <div style={{ marginTop: 12 }}>
            <Text strong>{result.intent === 'diagnose' ? '同组件的原文恢复入口（尚未执行）' : '2. 仓库原文中的要求与操作'}</Text>
            {result.sub_steps.some((child) => !child.command) && <ul style={{ paddingLeft: 20 }}>
              {result.sub_steps.filter((child) => !child.command).map((child) => <li key={child.step_id} style={{ marginBottom: 10 }}>
                <Text style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{child.evidence.quote}</Text>{' '}
                <EvidenceBadge guide={{ ...guide, default_branch: result.revision }} ev={child.evidence} />
              </li>)}
            </ul>}
            {result.sub_steps.filter((child) => child.command).map((child) => <Card key={child.step_id} size="small" style={{ marginTop: 8 }}>
              <Text strong>{child.title}</Text>
              {child.command && <>
                <Paragraph type="secondary" style={{ marginTop: 8 }}>执行位置：{child.directory_basis === 'clone_destination' ? '你选择的项目存放目录' : child.working_directory === '.' ? '仓库根目录' : child.working_directory || '尚未确认，请先核对出处'}</Paragraph>
                <Paragraph copyable={{ text: child.command }} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><Text code>{child.command}</Text></Paragraph>
              </>}
              {!child.command && <Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{child.evidence.quote}</Paragraph>}
              <Paragraph type="secondary">{child.expected}</Paragraph>
              <EvidenceBadge guide={{ ...guide, default_branch: result.revision }} ev={child.evidence} />
            </Card>)}
          </div>}
          {Boolean(result.completion_checks?.length) && <div style={{ marginTop: 12 }}>
            <Text strong>{result.intent === 'granular' ? '3. 如何判断与继续（工具提供）' : '如何判断与继续（工具提供）'}</Text>
            <ol>{result.completion_checks!.map((item) => <li key={item}>{item}</li>)}</ol>
          </div>}
          <GuideNotices guide={{ ...guide, default_branch: result.revision }} warnings={result.warnings} />
          {Boolean(result.local_checks?.length) && <div style={{ marginTop: 12 }}>
            <Text strong>通用本机检查（工具提供，非仓库原文）</Text>
            <Paragraph type="secondary">以下命令只读检查本机状态，没有替你执行。请在当前步骤要求的目录和开发环境中运行，并依据实际输出判断。</Paragraph>
            {result.local_checks!.map((check, i) => <div key={i} style={{ marginTop: 10 }}>
              <Text strong>{i + 1}. {check.label}</Text>
              <Paragraph copyable={{ text: check.command }} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: 4 }}><Text code>{check.command}</Text></Paragraph>
              <Paragraph>{check.expected}</Paragraph>
            </div>)}
          </div>}
          {result.evidence?.length ? result.evidence.map((ev, i) => <div key={i} style={{ marginTop: 10 }}>
            <EvidenceBadge guide={{ ...guide, default_branch: result.revision }} ev={ev} />
            <details open={i === 0}>
              <summary style={{ cursor: 'pointer', marginTop: 4 }}>原文摘录{ev.line_start ? `（L${ev.line_start}${ev.line_end && ev.line_end !== ev.line_start ? `-L${ev.line_end}` : ''}）` : ''}</summary>
              <Paragraph style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{ev.quote}</Paragraph>
            </details>
          </div>) : <Text type="secondary">未找到可核验的仓库原文，请先核对资料。</Text>}
        </Card>
      )}
    </div>
  )
}

// ---- Evidence panel (right rail) ------------------------------------------

function EvidencePanel({ guide, step }: { guide: Guide; step: GuideStep | null }) {
  if (!step) {
    return (
      <Card size="small" title="证据面板">
        <Empty description="点击步骤查看其来源" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    )
  }
  const ev = step.evidence
  const href = evidenceHref(guide, ev)
  return (
    <Card
      size="small"
      title={
        <Space>
          <FileTextOutlined /> 证据面板
        </Space>
      }
    >
      <Text strong>当前步骤：</Text>
      <Paragraph style={{ marginTop: 2 }}>{step.title}</Paragraph>
      {ev.kind === 'missing' ? (
        <Tag color="red" icon={<WarningOutlined />}>
          未找到通过核验的出处，请先确认原文
        </Tag>
      ) : (
        <div>
          <Text type="secondary">证据来源</Text>
          <div style={{ marginTop: 4 }}>
            <EvidenceBadge guide={guide} ev={ev} />
          </div>
          <Paragraph style={{ marginTop: 8 }}>
            {ev.verification === 'command_verified' ? step.execution_record ? '命令已匹配原文，附带固定环境的历史执行记录' : '命令已匹配原文，尚未执行验证' : ev.verification === 'quote_verified' ? '引用已匹配原文，建议仍需结合上下文判断' : '仅确认来源存在，尚未核验内容支持关系'}
          </Paragraph>
          {ev.quote && <Paragraph style={{ whiteSpace: 'pre-wrap' }}><Text code>{ev.quote}</Text></Paragraph>}
          {href && (
            <Button
              size="small"
              type="link"
              href={href}
              target="_blank"
              style={{ paddingLeft: 0 }}
            >
              打开原始出处 ↗
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}

// ---- Wizard body ----------------------------------------------------------

// Actual values are user-entered; never fill them from suggested guide commands.
function ExecutionFields({ execution, onChange }: { execution: LearningExecution; onChange: (value: LearningExecution) => void }) {
  return <div style={{ display: 'grid', gap: 10 }}>
    <label>执行情况<select aria-label="实际执行情况" value={execution.status} style={{ display: 'block', width: '100%', padding: 8 }}
      onChange={(event) => onChange({ ...execution, status: event.target.value as LearningExecution['status'] })}>
      {Object.entries(executionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    {([['command', '实际执行命令', '填写你实际运行的命令（可与指南不同）'], ['directory', '实际执行目录', '例如：项目副本/backend'],
      ['exitCode', '实际退出码', '例如 0 或 1；未知时留空'], ['scope', '实际运行范围', '例如：仅后端单元测试；未测前端'] ] as const).map(([field, label, placeholder]) =>
      <label key={field}>{label}<Input aria-label={label} placeholder={placeholder} maxLength={field === 'exitCode' ? 20 : 1000}
        value={execution[field]} onChange={(event) => onChange({ ...execution, [field]: event.target.value })} /></label>)}
    <label>结果、失败与跳过项摘要<Input.TextArea aria-label="实际结果摘要" rows={3} maxLength={1000} showCount
      placeholder="按实际输出记录通过、失败、跳过或超时情况；不填原始日志" value={execution.summary}
      onChange={(event) => onChange({ ...execution, summary: event.target.value })} /></label>
  </div>
}

function GuideSession({ guide, url, onRegenerateAi, onRegenerate }: {
  guide: Guide; url: string; onRegenerateAi?: () => void; onRegenerate?: () => void
}) {
  const steps = guide.steps
  const [progress, setProgress] = useState<LearningProgress>(() => {
    try { return loadLearningProgress(guide, window.localStorage) } catch { return emptyLearningProgress(guide) }
  })
  const [storageFailed, setStorageFailed] = useState(false)
  const [diagnosticStep, setDiagnosticStep] = useState<number | null>(null)
  const stepAnchor = useRef<HTMLDivElement>(null)
  const navigationRequested = useRef(false)
  const current = Math.max(0, steps.findIndex((s) => s.step_id === progress.currentStepId))
  const done = new Set(steps.flatMap((s, i) => progress.records[String(s.step_id)]?.status === 'done' ? [i] : []))

  const step = steps[current] ?? null
  const allDone = steps.length > 0 && done.size === steps.length
  const prerequisites = step ? pendingPrerequisites(guide, step, progress) : []
  const record = step ? progress.records[String(step.step_id)] : undefined
  const execution = record?.execution ?? emptyExecution()
  const resultProblems = executionProblems(record?.execution)
  const canAsk = !guide.is_demo && !guide.is_saved
  // Save on arrival, even if the user never navigates or records progress.
  // An idle tab may be discarded by the browser and later mounted again.
  // This effect reports an external storage write result, not derived UI state.
  /* oxlint-disable react/set-state-in-effect */
  useEffect(() => {
    try { setStorageFailed(!rememberLearningGuide(guide, window.localStorage)) }
    catch { setStorageFailed(true) }
  }, [guide])
  /* oxlint-enable react/set-state-in-effect */
  useEffect(() => {
    if (!navigationRequested.current) return
    stepAnchor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    navigationRequested.current = false
  }, [current])

  function persist(next: LearningProgress) {
    setProgress(next)
    try {
      const progressSaved = saveLearningProgress(next, window.localStorage)
      const guideSaved = rememberLearningGuide(guide, window.localStorage)
      setStorageFailed(!progressSaved || !guideSaved)
    } catch { setStorageFailed(true) }
  }
  function goToIndex(index: number) {
    if (!steps[index]) return
    if (index === current) stepAnchor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    else navigationRequested.current = true
    setDiagnosticStep(null)
    persist({ ...progress, currentStepId: steps[index].step_id })
  }
  function recordStatus(status: LearningStatus, advance = false) {
    if (!step) return
    if (advance && current < steps.length - 1) navigationRequested.current = true
    persist({ ...progress, records: { ...progress.records, [String(step.step_id)]: updateLearningRecord(record, { status }) },
      currentStepId: advance ? (steps[current + 1]?.step_id ?? step.step_id) : step.step_id })
    if (advance) setDiagnosticStep(null)
  }
  function markBlocked() {
    recordStatus('blocked')
    if (step && canAsk) setDiagnosticStep(step.step_id)
  }
  function downloadLearning() {
    const href = URL.createObjectURL(new Blob([learningMarkdown(guide, progress)], { type: 'text/markdown;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = href; link.download = `OpenGuide-${guide.owner}-${guide.repo}-learning.md`; link.click(); URL.revokeObjectURL(href)
  }

  const stepItems = useMemo(
    () =>
      Object.entries(STAGE_META).map(([stage, meta]) => ({
        title: meta.label,
        description: `${steps.filter((s) => s.stage === stage).length} 步`,
        disabled: !steps.some((s) => s.stage === stage),
      })),
    [steps],
  )

  function markDone() {
    if (resultProblems.length) { void message.warning('执行记录有待核对项，请先修正或如实保留为失败、超时、未运行。'); return }
    const completingAll = !done.has(current) && done.size + 1 === steps.length
    recordStatus('done', true)
    if (current === steps.length - 1 && completingAll) {
      void message.success('已标记全部步骤，请结合实际测试和 PR 状态核对结果。')
    }
  }

  if (guide.unsuitable) {
    return (
      <Card style={{ marginTop: 16 }}>
        <Title level={5}>暂不建议直接贡献此仓库</Title>
        <ul>
          {guide.reasons.map((r, i) => (
            <li key={i}>
              <Text type="secondary">{r}</Text>
            </li>
          ))}
        </ul>
      </Card>
    )
  }

  if (steps.length === 0) {
    return (
      <Card style={{ marginTop: 16 }}>
        <Empty description="（该仓库文档不足或生成器未输出步骤）" />
      </Card>
    )
  }

  return (
    <div className="guide-layout">
      {/* Main column: steps + current card */}
      <div className="guide-main">
        <GuideStatus guide={guide} step={step} onRegenerateAi={onRegenerateAi} onRegenerate={onRegenerate} />
        {!guide.is_demo && <Alert showIcon type={storageFailed ? 'warning' : 'info'} style={{ marginBottom: 12 }}
          message={storageFailed ? '本机自动保存失败，请下载指南 JSON 备份' : '路线图已自动保存在此浏览器，没有定时过期'}
          description="刷新或重新打开同一网址会恢复上次路线图，不重新调用模型。仅保留最近一份；清除站点数据、更换浏览器或网址后无法恢复。贡献表单、PR 草稿和问答历史不在此快照中，请单独导出。" />}
        {step && <LearningOverview guide={guide} step={step} progress={progress} onGo={(id) => goToIndex(steps.findIndex((s) => s.step_id === id))}
          onDownload={downloadLearning} onDownloadGuide={() => downloadGuide(guide)} storageFailed={storageFailed} />}
        {step?.stage === 'A' && steps.some((s) => /^(?:python(?:3)?\b|pip(?:3)?\b)/.test(s.command || '')) && <details style={{ marginBottom: 12 }}>
          <summary style={{ cursor: 'pointer' }}>Python 新手：先确认隔离环境与解释器</summary>
          <Paragraph style={{ marginTop: 8 }}>优先遵循仓库指定的运行时和环境工具。以下是 OpenGuide 提供的通用 venv 方法，不是仓库原文；先进入仓库，再创建开发环境。发布环境不能代替开发环境。</Paragraph>
          <Text strong>Windows PowerShell</Text>
          <Paragraph copyable={{ text: 'python -m venv .venv' }}><Text code>python -m venv .venv</Text></Paragraph>
          <Paragraph>无需修改执行策略或激活脚本，可直接指定环境解释器：</Paragraph>
          <Paragraph copyable={{ text: '.\\.venv\\Scripts\\python.exe -m pip --version' }}><Text code>{'.\\.venv\\Scripts\\python.exe -m pip --version'}</Text></Paragraph>
          <Paragraph>执行下面的 Python 命令时，把开头的 python 换成 <Text code>{'.\\.venv\\Scripts\\python.exe'}</Text>；若开头是 pip，改用该解释器的 <Text code>-m pip</Text>。</Paragraph>
          <Text strong>macOS / Linux</Text>
          <Paragraph copyable={{ text: 'python3 -m venv .venv\n.venv/bin/python -m pip --version' }} style={{ whiteSpace: 'pre-wrap' }}><Text code>{'python3 -m venv .venv\n.venv/bin/python -m pip --version'}</Text></Paragraph>
          <Paragraph>继续使用 <Text code>.venv/bin/python</Text> 运行仓库要求的 Python 命令。创建失败时先检查运行时版本及系统 venv 支持，避免把依赖直接装进系统 Python。</Paragraph>
        </details>}
        <Steps
          current={['A', 'B', 'C', 'D'].indexOf(step?.stage ?? 'A')}
          size="small"
          items={stepItems.map((it, i) => ({
            ...it,
            status: steps.some((s) => s.stage === ['A', 'B', 'C', 'D'][i]) && steps.every((s, n) => s.stage !== ['A', 'B', 'C', 'D'][i] || done.has(n)) ? 'finish' : step?.stage === ['A', 'B', 'C', 'D'][i] ? 'process' : 'wait',
          }))}
          onChange={(stageIndex) => {
            const first = steps.findIndex((s) => s.stage === ['A', 'B', 'C', 'D'][stageIndex])
            if (first >= 0) goToIndex(first)
          }}
          labelPlacement="vertical"
          responsive={false}
        />

        {step && (
          <Card
            className="guide-step-card"
            style={{ marginTop: 16 }}
            title={
              <Space>
                <Tag color={STAGE_META[step.stage]?.color}>{step.stage}</Tag>
                <Text strong>{step.stage_label || STAGE_META[step.stage]?.label}</Text>
              </Space>
            }
          >
            <div ref={stepAnchor} style={{ scrollMarginTop: 100 }} />
            <Title level={5} style={{ marginTop: 0 }}>
              第 {current + 1}/{steps.length} 步 · {step.title}
            </Title>
            {step.ai_explanation && <Alert showIcon type="info" style={{ marginBottom: 12 }}
              message={step.ai_explanation_basis === 'general' ? 'AI 讲解 · 通用准备，仍需核对仓库要求' : 'AI 逐步讲解 · 操作与出处由原文固定'}
              description={step.ai_explanation} />}
            {step.generation_source && step.generation_source !== 'unknown' && <Tag color={step.generation_source === 'llm' ? 'blue' : 'default'}>
              {step.generation_source === 'llm' ? '本步由 AI 生成，操作与引用另经原文核对' : '本步为原文规则整理'}
            </Tag>}

            {step.command && <Paragraph>
              <Text strong>{step.directory_basis === 'build_file' ? '建议执行位置（按构建文件推导）：' : step.directory_basis === 'document_context' ? '建议执行位置（按原文上下文推导）：' : '执行位置：'}</Text>{step.directory_basis === 'clone_destination' ? '你选择的项目存放目录（克隆后进入仓库）' : step.working_directory === '.' ? '仓库根目录' : step.working_directory || '待确认，请先核对来源中的目录说明'}
            </Paragraph>}
            {Boolean(step.prerequisite_step_ids?.length) && <Paragraph><Text strong>建议先完成：</Text>第 {step.prerequisite_step_ids!.join('、')} 步（流程顺序，不代表依赖已验证）</Paragraph>}
            {prerequisites.length > 0 && <Alert type="info" showIcon message="这些前置步骤尚未记录完成"
              description={<Space wrap>{prerequisites.map((item) => <Button key={item.step_id} size="small" onClick={() => goToIndex(steps.findIndex((s) => s.step_id === item.step_id))}>回到第 {item.step_id} 步</Button>)}</Space>}
              style={{ marginBottom: 12 }} />}
            {Boolean(step.required_paths?.length) && <Paragraph><Text strong>所需输入路径：</Text>{step.required_paths!.join('、')}</Paragraph>}
            {Boolean(step.missing_inputs?.length) && <Alert type="error" showIcon message={`在当前文件树中未找到：${step.missing_inputs!.join('、')}；请先确认目录、分支和依赖文件`} style={{ marginBottom: 10 }} />}
            {step.context_notes?.map((note, i) => <Paragraph type="secondary" key={i}>{note}</Paragraph>)}

            {step.command && (
              <div>
              <pre className="command-block">
                <code>{step.command}</code>
              </pre>
              <Typography.Text copyable={{ text: step.command }}>复制完整命令</Typography.Text>
              </div>
            )}

            {step.expected && (
              <Paragraph style={{ marginBottom: 4 }}>
                <Text strong>本步核对目标：</Text>{step.expected}
              </Paragraph>
            )}
            {step.command_derivation && <Paragraph type="secondary">{step.command_derivation}（原建议：{step.original_command}）</Paragraph>}
            {Boolean(step.success_checks?.length) && <div style={{ marginTop: 8, marginBottom: 8 }}><Text strong>基础完成检查（通用）：</Text>{step.success_checks!.map((check, i) => <Paragraph key={i} style={{ marginBottom: 4 }}>{check}</Paragraph>)}</div>}
            {step.execution_record && <Alert showIcon
              type={step.execution_record.status === 'passed' ? 'success' : 'error'}
              message={`历史执行记录：${step.execution_record.status === 'passed' ? '通过' : step.execution_record.status === 'timed_out' ? '超时' : '失败'}`}
              description={`${step.execution_record.summary}；环境：${step.execution_record.environment}。仅适用于记录中的提交与环境，不代表当前机器已验证。`}
              style={{ marginTop: 10, marginBottom: 10 }} />}

            {step.fail_hints?.some((h) => !h.startsWith('模型的来源类型字段') && !h.startsWith('引用中的空白格式')) && (
              <div style={{ marginTop: 6 }}>
                {step.fail_hints.filter((h) => !h.startsWith('模型的来源类型字段') && !h.startsWith('引用中的空白格式')).map((h, i) => (
                  <Text type="warning" key={i} style={{ display: 'block' }}>
                    ⚠ {h}
                  </Text>
                ))}
              </div>
            )}
            {step.fail_hints?.some((h) => h.startsWith('模型的来源类型字段') || h.startsWith('引用中的空白格式')) && <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer' }}>引用核对记录</summary>
              {step.fail_hints.filter((h) => h.startsWith('模型的来源类型字段') || h.startsWith('引用中的空白格式')).map((h) => <Paragraph key={h} type="secondary" style={{ marginTop: 6 }}>{h}</Paragraph>)}
            </details>}

            <div style={{ marginTop: 8 }}>
              <EvidenceBadge guide={guide} ev={step.evidence} />
            </div>

            <GuideEntryHelp guide={guide} stage={step.stage} expanded={step.evidence.kind === 'missing'} />
            {canAsk && <FollowupBar key={`${guide.default_branch}:${step.step_id}`} step={step} url={url} guide={guide}
              logOpen={diagnosticStep === step.step_id} onBlocked={markBlocked} onToggleLog={() => setDiagnosticStep(null)} />}
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #e7efec' }}>
              <Text strong>本步记录（仅本机）</Text>{' '}<Tag>{learningLabels[record?.status ?? 'pending']}</Tag>
              <Paragraph type="secondary" style={{ marginTop: 6, marginBottom: 8 }}>{nextLearningAction(step, progress, prerequisites, canAsk)}</Paragraph>
              <Input.TextArea aria-label="本步结果或卡点摘要" rows={2} maxLength={1000} showCount value={record?.note ?? ''}
                placeholder={step.stage === 'C' ? '记录任务来源、复现方式、范围与验收方法' : step.stage === 'D' ? '记录实际修改、验证范围和待审阅事项' : '记录实际目录、退出码或卡点摘要；不要填写密钥或原始日志'}
                onChange={(event) => persist({ ...progress, records: { ...progress.records, [String(step.step_id)]: updateLearningRecord(record, { note: event.target.value }) } })} />
              {step.command && <details style={{ marginTop: 16 }} open={record?.execution !== undefined}>
                <summary style={{ cursor: 'pointer' }}>实际执行记录 · {executionLabels[execution.status]}</summary>
                <Paragraph type="secondary" style={{ marginTop: 8 }}>自行填写并仅保存在本机，工具未执行或核验。实际值不会从指南自动填入；通过不代表完整测试通过。导出学习记录会包含这些内容，请勿填写密钥、个人路径或原始日志。</Paragraph>
                <ExecutionFields execution={execution} onChange={(next) => persist({ ...progress, records: { ...progress.records,
                  [String(step.step_id)]: updateLearningRecord(record, { execution: next }) } })} />
                {resultProblems.length > 0 && <Alert type="warning" showIcon message="执行记录待核对" description={<ul>{resultProblems.map((problem) => <li key={problem}>{problem}</li>)}</ul>} style={{ marginTop: 8 }} />}
                <Paragraph type="secondary" style={{ marginTop: 8 }}>学习进度与执行情况独立；未运行、失败、跳过项会如实保留在导出中。</Paragraph>
              </details>}
              <Space wrap style={{ marginTop: 14 }}>
                <Button onClick={markBlocked}>我卡住了{canAsk ? '，展开排错' : ''}</Button>
                <Button onClick={() => recordStatus('skipped', true)}>暂缓，继续浏览</Button>
                {record && record.status !== 'pending' && <Button type="link" onClick={() => recordStatus('pending')}>{record.status === 'done' ? '撤回本步完成标记' : '改为待继续'}</Button>}
              </Space>
            </div>
          </Card>
        )}

        {!guide.is_demo && <ContributionWorkbench guide={guide} stage={step?.stage ?? ''} records={progress.records}
          onExploreStep={(id) => goToIndex(steps.findIndex(s => s.step_id === id))} />}

        {allDone && (
          <Alert
            showIcon
            type="success"
            message={`你已手动标记全部 ${steps.length} 个步骤`}
            description="这是手动进度记录。请结合测试结果和 GitHub 上的实际 PR 状态确认贡献完成情况。"
            style={{ marginTop: 16 }}
            action={
              <Button size="small" onClick={() => goToIndex(0)}>
                返回第一步
              </Button>
            }
          />
        )}

        <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between' }}>
          <Button
            icon={<LeftOutlined />}
            disabled={current === 0}
            onClick={() => goToIndex(current - 1)}
          >
            上一步
          </Button>
          {current < steps.length - 1 && <Button onClick={() => goToIndex(current + 1)}>仅查看下一步</Button>}
          {current < steps.length - 1 ? (
            <Button type="primary" onClick={markDone}>
              记为已核对并继续 <RightOutlined />
            </Button>
          ) : (
            <Button type="primary" icon={<CheckCircleOutlined />} disabled={allDone} onClick={markDone}>
              {allDone ? '已记录全部完成' : '记录本步已核对'}
            </Button>
          )}
        </div>
      </div>

      {/* Right rail: evidence panel */}
      <div className="guide-evidence">
        <EvidencePanel guide={guide} step={step} />
      </div>
    </div>
  )
}

export default function GuideWizard(props: { guide: Guide; url: string; onRegenerateAi?: () => void; onRegenerate?: () => void }) {
  return <GuideSession key={learningIdentity(props.guide)} {...props} />
}
