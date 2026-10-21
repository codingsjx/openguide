import { useMemo, useState } from 'react'
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
}: {
  step: GuideStep
  url: string
  guide: Guide
}) {
  const [logOpen, setLogOpen] = useState(false)
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
        <Button size="small" disabled={!!busy} icon={<BugOutlined />} loading={busy === 'diagnose'} onClick={() => setLogOpen((v) => !v)}>
          报错了
        </Button>
      </Space>

      {logOpen && (
        <div style={{ marginTop: 8 }}>
          <Paragraph type="secondary">日志可能交给当前配置的模型服务分析；粘贴前请移除密钥、账号及个人信息。</Paragraph>
          <Input.TextArea
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
          {result.warnings?.map((warning, i) => <Alert key={i} type="warning" message={warning} style={{ marginBottom: 8 }} />)}
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

export default function GuideWizard({ guide, url }: { guide: Guide; url: string }) {
  const steps = guide.steps
  const [current, setCurrent] = useState(0)
  const [done, setDone] = useState<Set<number>>(new Set())

  const step = steps[current] ?? null
  const allDone = steps.length > 0 && done.size === steps.length

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
    const completingAll = !done.has(current) && done.size + 1 === steps.length
    setDone((prev) => {
      const next = new Set(prev)
      next.add(current)
      return next
    })
    if (current < steps.length - 1) {
      setCurrent((c) => c + 1)
    } else if (completingAll) {
      void message.success('已标记全部步骤，请结合实际测试和 PR 状态核对结果。')
    }
  }

  function resetProgress() {
    setDone(new Set())
    setCurrent(0)
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
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 16, alignItems: 'flex-start' }}>
      {/* Main column: steps + current card */}
      <div style={{ flex: 1, minWidth: 280 }}>
        <Alert type="info" showIcon style={{ marginBottom: 12 }} message={guide.is_saved ? '已保存指南，未重新联网核验' : guide.is_demo ? '静态交互示例，未分析仓库' : guide.generation_mode === 'mixed' ? 'AI 生成与仓库原文展开；命令仍需本地验证' : guide.generation_mode === 'llm' ? '本次使用 AI 生成；命令仍需在本地验证' : '本次使用规则生成；配置模型后可启用 AI 生成'} />
        {guide.warnings?.map((warning) => <Alert key={warning} type="warning" message={warning} style={{ marginBottom: 8 }} />)}
        <Steps
          current={['A', 'B', 'C', 'D'].indexOf(step?.stage ?? 'A')}
          size="small"
          items={stepItems.map((it, i) => ({
            ...it,
            status: steps.some((s) => s.stage === ['A', 'B', 'C', 'D'][i]) && steps.every((s, n) => s.stage !== ['A', 'B', 'C', 'D'][i] || done.has(n)) ? 'finish' : step?.stage === ['A', 'B', 'C', 'D'][i] ? 'process' : 'wait',
          }))}
          onChange={(stageIndex) => {
            const first = steps.findIndex((s) => s.stage === ['A', 'B', 'C', 'D'][stageIndex])
            if (first >= 0) setCurrent(first)
          }}
          labelPlacement="vertical"
          responsive
        />

        {step && (
          <Card
            style={{ marginTop: 16 }}
            title={
              <Space>
                <Tag color={STAGE_META[step.stage]?.color}>{step.stage}</Tag>
                <Text strong>{step.stage_label || STAGE_META[step.stage]?.label}</Text>
              </Space>
            }
          >
            <Title level={5} style={{ marginTop: 0 }}>
              第 {current + 1}/{steps.length} 步 · {step.title}
            </Title>

            {step.command && <Paragraph>
              <Text strong>{step.directory_basis === 'build_file' ? '建议执行位置（按构建文件推导）：' : '执行位置：'}</Text>{step.directory_basis === 'clone_destination' ? '你选择的项目存放目录（克隆后进入仓库）' : step.working_directory === '.' ? '仓库根目录' : step.working_directory || '待确认，请先核对来源中的目录说明'}
            </Paragraph>}
            {Boolean(step.prerequisite_step_ids?.length) && <Paragraph><Text strong>建议先完成：</Text>第 {step.prerequisite_step_ids!.join('、')} 步（流程顺序，不代表依赖已验证）</Paragraph>}
            {Boolean(step.required_paths?.length) && <Paragraph><Text strong>所需输入路径：</Text>{step.required_paths!.join('、')}</Paragraph>}
            {Boolean(step.missing_inputs?.length) && <Alert type="error" showIcon message={`在当前文件树中未找到：${step.missing_inputs!.join('、')}；请先确认目录、分支和依赖文件`} style={{ marginBottom: 10 }} />}
            {step.context_notes?.map((note, i) => <Paragraph type="secondary" key={i}>{note}</Paragraph>)}

            {step.command && (
              <pre
                style={{
                  background: '#f6f8fa',
                  padding: '10px 12px',
                  borderRadius: 6,
                  overflowX: 'auto',
                  fontSize: 13,
                  margin: '8px 0',
                }}
              >
                <code>{step.command}</code>
              </pre>
            )}

            {step.expected && (
              <Paragraph style={{ marginBottom: 4 }}>
                <CheckCircleOutlined style={{ color: '#52c41a' }} /> 期望：{step.expected}
              </Paragraph>
            )}
            {step.command_derivation && <Paragraph type="secondary">{step.command_derivation}（原建议：{step.original_command}）</Paragraph>}
            {Boolean(step.success_checks?.length) && <div style={{ marginTop: 8, marginBottom: 8 }}><Text strong>基础完成检查（通用）：</Text>{step.success_checks!.map((check, i) => <Paragraph key={i} style={{ marginBottom: 4 }}>{check}</Paragraph>)}</div>}
            {step.execution_record && <Alert showIcon
              type={step.execution_record.status === 'passed' ? 'success' : 'error'}
              message={`历史执行记录：${step.execution_record.status === 'passed' ? '通过' : step.execution_record.status === 'timed_out' ? '超时' : '失败'}`}
              description={`${step.execution_record.summary}；环境：${step.execution_record.environment}。仅适用于记录中的提交与环境，不代表当前机器已验证。`}
              style={{ marginTop: 10, marginBottom: 10 }} />}

            {step.fail_hints && step.fail_hints.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {step.fail_hints.map((h, i) => (
                  <Text type="warning" key={i} style={{ display: 'block' }}>
                    ⚠ {h}
                  </Text>
                ))}
              </div>
            )}

            <div style={{ marginTop: 8 }}>
              <EvidenceBadge guide={guide} ev={step.evidence} />
            </div>

            {!guide.is_demo && !guide.is_saved && <FollowupBar key={`${guide.default_branch}:${step.step_id}`} step={step} url={url} guide={guide} />}
          </Card>
        )}

        {allDone && (
          <Alert
            showIcon
            type="success"
            message={`你已手动标记全部 ${steps.length} 个步骤`}
            description="这是手动进度记录。请结合测试结果和 GitHub 上的实际 PR 状态确认贡献完成情况。"
            style={{ marginTop: 16 }}
            action={
              <Button size="small" onClick={resetProgress}>
                重新开始
              </Button>
            }
          />
        )}

        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Button
            icon={<LeftOutlined />}
            disabled={current === 0}
            onClick={() => setCurrent((c) => c - 1)}
          >
            上一步
          </Button>
          {current < steps.length - 1 ? (
            <Button type="primary" onClick={markDone}>
              完成并下一步 <RightOutlined />
            </Button>
          ) : (
            <Button type="primary" icon={<CheckCircleOutlined />} disabled={allDone} onClick={markDone}>
              {allDone ? '已全部完成' : '完成全部'}
            </Button>
          )}
        </div>
      </div>

      {/* Right rail: evidence panel */}
      <div style={{ width: 260, flexShrink: 0, maxWidth: '100%' }}>
        <EvidencePanel guide={guide} step={step} />
      </div>
    </div>
  )
}
