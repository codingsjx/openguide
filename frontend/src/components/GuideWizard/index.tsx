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

import { api } from '../../api/client'
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
    return `${guide.repo_url}/blob/${guide.default_branch ?? 'main'}/${path}${
      line ? `#L${line.replace('L', '')}` : ''
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
}: {
  step: GuideStep
  url: string
}) {
  const [logOpen, setLogOpen] = useState(false)
  const [logText, setLogText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [result, setResult] = useState<{ intent: string; text: string } | null>(null)

  async function run(intent: 'granular' | 'explain' | 'diagnose') {
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
        step: { title: step.title, command: step.command, stage: step.stage, expected: step.expected },
        log_text: intent === 'diagnose' ? logText : '',
      })
      setResult({ intent, text: r.text })
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '追问失败')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <Space wrap size={6}>
        <Button size="small" icon={<ZoomInOutlined />} loading={busy === 'granular'} onClick={() => run('granular')}>
          这步太粗
        </Button>
        <Button size="small" icon={<QuestionCircleOutlined />} loading={busy === 'explain'} onClick={() => run('explain')}>
          看不懂为什么
        </Button>
        <Button size="small" icon={<BugOutlined />} loading={busy === 'diagnose'} onClick={() => setLogOpen((v) => !v)}>
          报错了
        </Button>
      </Space>

      {logOpen && (
        <div style={{ marginTop: 8 }}>
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
          该项目文档未提供此步出处（无证据不宣称）
        </Tag>
      ) : (
        <div>
          <Text type="secondary">证据来源</Text>
          <div style={{ marginTop: 4 }}>
            <EvidenceBadge guide={guide} ev={ev} />
          </div>
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
      steps.map((s) => ({
        title: (
          <Space size={4}>
            <Tag color={STAGE_META[s.stage]?.color} style={{ marginRight: 0 }}>
              {s.stage}
            </Tag>
            <span>{s.title}</span>
          </Space>
        ),
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
      void message.success('恭喜，你已完成全部贡献步骤！')
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
        <Steps
          current={current}
          size="small"
          items={stepItems.map((it, i) => ({
            ...it,
            status: done.has(i) ? 'finish' : i === current ? 'process' : 'wait',
          }))}
          labelPlacement="vertical"
          responsive={false}
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
              Step {step.step_id} · {step.title}
            </Title>

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

            <FollowupBar step={step} url={url} />
          </Card>
        )}

        {allDone && (
          <Alert
            showIcon
            type="success"
            message={`你已完成全部 ${steps.length} 个步骤`}
            description="路线图已走完。提交 PR 后，记得关注评审意见并及时回复维护者。"
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
