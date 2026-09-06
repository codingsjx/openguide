import { Card, Space, Tag, Timeline, Typography } from 'antd'
import {
  FileTextOutlined,
  LinkOutlined,
  WarningOutlined,
} from '@ant-design/icons'

import type { Guide, GuideStep } from '../../types/guide'

const { Paragraph, Text, Title } = Typography

const STAGE_COLOR: Record<string, string> = {
  A: 'blue',
  B: 'purple',
  C: 'green',
  D: 'orange',
}

function EvidenceTag({ step }: { step: GuideStep }) {
  const ev = step.evidence
  if (ev.kind === 'missing') {
    return (
      <Tag color="red" icon={<WarningOutlined />}>
        无来源标注
      </Tag>
    )
  }
  if (ev.kind === 'issue') {
    return (
      <Tag color="green" icon={<LinkOutlined />}>
        来自 issue {ev.source}
      </Tag>
    )
  }
  return (
    <Tag color="cyan" icon={<FileTextOutlined />}>
      来自 {ev.source}
    </Tag>
  )
}

export default function GuideDisplay({ guide }: { guide: Guide }) {
  if (guide.unsuitable) {
    return (
      <Card style={{ maxWidth: 900, margin: '0 auto', marginTop: 16 }}>
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

  // Group steps by stage, preserving order A→D.
  const order = { A: 0, B: 1, C: 2, D: 3 }
  const byStage = new Map<string, GuideStep[]>()
  for (const s of guide.steps) {
    const arr = byStage.get(s.stage) ?? []
    arr.push(s)
    byStage.set(s.stage, arr)
  }
  const stageKeys = [...byStage.keys()].sort((a, b) => (order[a as keyof typeof order] ?? 9) - (order[b as keyof typeof order] ?? 9))

  return (
    <div style={{ marginTop: 16 }}>
      <Title level={5} style={{ marginBottom: 4 }}>
        分步贡献指南 · {guide.owner}/{guide.repo}
      </Title>
      {guide.steps.length === 0 ? (
        <Paragraph type="secondary">（暂无生成步骤——该仓库文档不足或生成器未输出。）</Paragraph>
      ) : (
        stageKeys.map((stage) => (
          <Card
            key={stage}
            size="small"
            style={{ marginBottom: 12 }}
            title={
              <Space>
                <Tag color={STAGE_COLOR[stage]}>{stage}</Tag>
                <Text strong>{byStage.get(stage)?.[0]?.stage_label || stage}</Text>
              </Space>
            }
          >
            <Timeline
              items={(byStage.get(stage) ?? []).map((s) => ({
                color: s.evidence.kind === 'missing' ? 'red' : 'blue',
                children: (
                  <div>
                    <Space wrap style={{ marginBottom: 4 }}>
                      <Text strong>Step {s.step_id} · {s.title}</Text>
                      <EvidenceTag step={s} />
                    </Space>
                    {s.command && (
                      <pre
                        style={{
                          background: '#f6f8fa',
                          padding: '8px 10px',
                          borderRadius: 6,
                          overflowX: 'auto',
                          fontSize: 13,
                        }}
                      >
                        <code>{s.command}</code>
                      </pre>
                    )}
                    {s.expected && (
                      <Paragraph type="secondary" style={{ marginBottom: 2 }}>
                        ✓ 期望：{s.expected}
                      </Paragraph>
                    )}
                    {s.fail_hints && s.fail_hints.length > 0 && (
                      <div style={{ marginTop: 4 }}>
                        {s.fail_hints.map((h, i) => (
                          <Text type="warning" key={i} style={{ display: 'block' }}>
                            ⚠ {h}
                          </Text>
                        ))}
                      </div>
                    )}
                    {s.evidence.quote && (
                      <Paragraph type="secondary" style={{ marginTop: 6, fontStyle: 'italic' }}>
                        证据：{s.evidence.quote}
                      </Paragraph>
                    )}
                  </div>
                ),
              }))}
            />
          </Card>
        ))
      )}
    </div>
  )
}
