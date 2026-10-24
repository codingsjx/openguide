import type { ReactNode } from 'react'
import { Alert, Button, Space, Tag, Typography } from 'antd'
import type { Guide, GuideStep } from '../../types/guide'
import { fallbackLabels, groupGuideWarnings, guideStatus } from '../../types/guideStatus'

const { Paragraph, Text } = Typography
const labels = { A: '环境搭建', B: '测试基线', C: '挑选 issue', D: '首次 PR 路径' }

export function GuideNotices({ guide, warnings, generationDetails, onRegenerate }: {
  guide: Guide; warnings?: string[]; generationDetails?: ReactNode; onRegenerate?: () => void
}) {
  const groups = groupGuideWarnings(warnings)
  return <div style={{ marginBottom: 12 }}>
    {groups.collection.length > 0 && <Alert showIcon type="warning" style={{ marginBottom: 10 }}
      message={`生成时有 ${groups.collection.length} 条资料采集提示`}
      description={<>
        <Paragraph style={{ marginBottom: 4 }}>{groups.collection[0]}</Paragraph>
        <Text>这份指南只覆盖已取得的资料。</Text>
        {groups.collection.length > 1 && <details style={{ marginTop: 6 }}><summary style={{ cursor: 'pointer' }}>查看全部采集详情</summary>{groups.collection.map((text) => <Paragraph key={text} style={{ margin: '6px 0' }}>{text}</Paragraph>)}</details>}
        {onRegenerate && <div style={{ marginTop: 8 }}><Button size="small" onClick={onRegenerate}>{guide.requested_mode === 'rules' ? '按规则重新生成并重试采集' : '用 AI 重新生成并重试采集'}</Button></div>}
      </>} />}
    {groups.preparation.length > 0 && <details style={{ marginBottom: 8 }}>
      <summary style={{ cursor: 'pointer' }}>操作前核对（{groups.preparation.length} 项）· Windows 符号链接</summary>
      {groups.preparation.map((text) => <Paragraph key={text} style={{ margin: '8px 0' }}>{text}</Paragraph>)}
    </details>}
    {(generationDetails || groups.generation.length > 0) && <details style={{ marginBottom: 8 }}>
      <summary style={{ cursor: 'pointer' }}>生成详情与各阶段来源</summary>
      <div style={{ marginTop: 8 }}>{generationDetails}</div>
      {groups.generation.map((text) => <Paragraph key={text} type="secondary" style={{ marginBottom: 6 }}>{text}</Paragraph>)}
    </details>}
    <details style={{ marginBottom: 8 }}>
      <summary style={{ cursor: 'pointer', color: '#64748b' }}>资料版本与核验说明 · {guide.default_branch.slice(0, 12)}</summary>
      <Paragraph style={{ margin: '8px 0' }}><Text strong>引用版本：</Text><Text copyable={{ text: guide.default_branch }}>{guide.default_branch}</Text></Paragraph>
      <Paragraph>文件原文与 issue 快照分别采集；参与任务前核对最新讨论。原文匹配不代表命令已在本机执行。</Paragraph>
      {groups.reference.map((text) => <Paragraph key={text} type="secondary">{text}</Paragraph>)}
    </details>
    {groups.other.length > 0 && <details style={{ marginBottom: 8 }}>
      <summary style={{ cursor: 'pointer' }}>其他提示（{groups.other.length} 条）</summary>
      {groups.other.map((text) => <Paragraph key={text} style={{ margin: '8px 0' }}>{text}</Paragraph>)}
    </details>}
  </div>
}

export default function GuideStatus({ guide, step, onRegenerateAi, onRegenerate }: {
  guide: Guide; step: GuideStep | null; onRegenerateAi?: () => void; onRegenerate?: () => void
}) {
  const status = guideStatus(guide)
  const mode = step && guide.stage_modes?.[step.stage]
  const reason = step && guide.stage_fallbacks?.[step.stage]
  return <>
    <Alert showIcon type={status.type} message={status.title} style={{ marginBottom: 10 }}
      description={<>
        {status.description}
        {onRegenerateAi && (guide.requested_mode === 'rules' || Object.keys(guide.stage_fallbacks ?? {}).length > 0 || guide.requested_mode == null || guide.requested_mode === 'unknown')
          && <div style={{ marginTop: 8 }}><Button size="small" onClick={onRegenerateAi}>用 AI 重新生成</Button></div>}
      </>} />
    {step && mode && <Space wrap size={4} style={{ marginBottom: 8 }}>
      <Text type="secondary">当前 · {labels[step.stage]}</Text>
      <Tag color={mode !== 'heuristic' ? 'blue' : 'default'}>{mode === 'llm' ? 'AI 生成' : mode === 'mixed' ? 'AI + 原文补齐' : '规则整理'}</Tag>
      {reason && <Text type="secondary">{fallbackLabels[reason]}</Text>}
    </Space>}
    <GuideNotices guide={guide} warnings={guide.warnings} onRegenerate={onRegenerate}
      generationDetails={Object.keys(guide.stage_modes ?? {}).length > 0 || guide.model_request_attempts != null ? <>
      {guide.model_request_attempts != null && <Paragraph>模型实际请求 {guide.model_request_attempts} 次；连接提前关闭后重试 {guide.model_disconnect_retries ?? 0} 次。仅记录请求，不等于生成全部成功。</Paragraph>}
      {Object.keys(guide.stage_modes ?? {}).length > 0 ? Object.entries(labels).map(([stage, label]) => {
        const stageKey = stage as 'A' | 'B' | 'C' | 'D'
        const stageMode = guide.stage_modes?.[stageKey]
        const fallback = guide.stage_fallbacks?.[stageKey]
        return <Paragraph key={stage} style={{ marginBottom: 6 }}><Text strong>{label}：</Text>{stageMode === 'llm' ? 'AI 生成' : stageMode === 'mixed' ? 'AI + 原文规则补齐' : stageMode === 'heuristic' ? '规则整理' : '来源未记录'}{fallback ? `；${fallbackLabels[fallback]}` : ''}</Paragraph>
      }) : undefined}</> : undefined} />
  </>
}
