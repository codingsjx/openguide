import { Button, Card, Space, Tag, Typography } from 'antd'
import type { Guide, GuideStep } from '../types/guide'
import { learningLabels, phaseGoals, type LearningProgress } from '../types/learningProgress'

export default function LearningOverview({ guide, step, progress, onGo, onDownload, onDownloadGuide, storageFailed }: {
  guide: Guide; step: GuideStep; progress: LearningProgress; onGo: (id: number) => void; onDownload: () => void; onDownloadGuide: () => void; storageFailed: boolean
}) {
  const counts = { done: 0, blocked: 0, skipped: 0 }
  let executionRecords = 0
  for (const item of guide.steps) {
    const status = progress.records[String(item.step_id)]?.status
    if (status && status !== 'pending') counts[status]++
    const execution = progress.records[String(item.step_id)]?.execution
    if (execution && execution.status !== 'unrecorded') executionRecords++
  }
  return <Card size="small" style={{ marginBottom: 12, background: '#f4faf8' }}>
    <Typography.Text strong>本阶段要达到什么</Typography.Text>
    <Typography.Paragraph style={{ marginTop: 6, marginBottom: 8 }}>{phaseGoals[step.stage]}</Typography.Paragraph>
    <Space wrap><Tag color={counts.done ? 'green' : undefined}>自行核对 {counts.done}/{guide.steps.length}</Tag><Tag color={counts.blocked ? 'orange' : undefined}>卡住 {counts.blocked}</Tag><Tag>暂缓 {counts.skipped}</Tag><Button size="small" onClick={onDownload}>导出学习记录</Button>{guide.is_saved && <Button size="small" onClick={onDownloadGuide}>保存当前指南 JSON</Button>}</Space>
    <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 6 }}>已填写执行情况 {executionRecords} 项（含未运行、失败和超时），与阅读核对进度独立；均为用户记录，不代表工具执行验证。</Typography.Paragraph>
    {storageFailed && <Typography.Paragraph type="warning">当前无法保存部分本机数据，请离开前导出记录和指南。</Typography.Paragraph>}
    <details style={{ marginBottom: 6 }}>
      <summary style={{ cursor: 'pointer' }}>本机保存与恢复说明</summary>
      <Typography.Paragraph type="secondary" style={{ marginTop: 6, marginBottom: 6 }}>路线图生成后自动保存在当前浏览器，刷新后自动恢复上次指南及已记录的学习进度，新版本不混用。请勿填写密钥或原始日志。问答历史及贡献工作台表单不在此记录中；贡献表单可单独导出准备记录。</Typography.Paragraph>
    </details>
    <details>
      <summary style={{ cursor: 'pointer' }}>步骤目录 · 返回未完成项和卡点</summary>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {guide.steps.map((item) => <div key={item.step_id} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
          <Tag style={{ flexShrink: 0 }}>{learningLabels[progress.records[String(item.step_id)]?.status ?? 'pending']}</Tag>
          <Button type="link" aria-current={item.step_id === step.step_id ? 'step' : undefined} onClick={() => onGo(item.step_id)}
            style={{ height: 'auto', whiteSpace: 'normal', textAlign: 'left', padding: 0, overflowWrap: 'anywhere' }}>第 {item.step_id} 步 · {item.title}</Button>
        </div>)}
      </div>
    </details>
  </Card>
}
