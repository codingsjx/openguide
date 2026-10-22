import { useState } from 'react'
import { Alert, Button, Card, Input, Radio, Space, Tag, Typography } from 'antd'
import type { Guide } from '../../types/guide'
import { buildContributionDraft, changedFiles, contributionProblems, emptyContribution, type ContributionInput } from '../../types/contribution'

const { Paragraph, Text } = Typography

export default function ContributionWorkbench({ guide, stage }: { guide: Guide; stage: string }) {
  const [input, setInput] = useState(emptyContribution)
  const [draft, setDraft] = useState('')
  const discovery = guide.issue_discovery
  const sampledAt = discovery?.sampled_at && Number.isFinite(Date.parse(discovery.sampled_at))
    ? new Date(discovery.sampled_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）' : '未记录'
  const issuesUrl = guide.repo_url + '/issues'
  const update = <K extends keyof ContributionInput>(key: K, value: ContributionInput[K]) => {
    setInput((s) => ({ ...s, [key]: value }))
    setDraft('')
  }
  const problems = contributionProblems(guide, input)
  const choose = (url: string, title: string) => {
    setInput((s) => ({ ...s, issueUrl: url, task: title }))
    setDraft('')
  }
  const field = (key: keyof ContributionInput, label: string, placeholder: string, multiline = false) => <label style={{ display: 'block', marginTop: 12 }}>
    <Text strong>{label}</Text>
    {multiline ? <Input.TextArea aria-label={label} rows={3} maxLength={key === 'patch' ? 1_000_000 : 10000} value={input[key]} placeholder={placeholder} onChange={(e) => update(key, e.target.value as never)} />
      : <Input aria-label={label} value={input[key]} maxLength={1000} placeholder={placeholder} onChange={(e) => update(key, e.target.value as never)} />}
  </label>
  const download = () => {
    const url = URL.createObjectURL(new Blob([draft], { type: 'text/markdown;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url; a.download = `OpenGuide-${guide.owner}-${guide.repo}-pr-draft.md`; a.click(); URL.revokeObjectURL(url)
  }
  if (stage !== 'C' && stage !== 'D') return null
  return <Card title="贡献工作台：任务 → 改动 → PR 草稿" style={{ marginTop: 16 }}>
    <Paragraph type="secondary">填写内容仅保留在当前页面，不会发给模型或提交到 GitHub；离开或重新生成指南前请导出草稿。草稿会保留测试失败和未执行状态。</Paragraph>
    <Alert type={discovery?.status === 'candidates' ? 'info' : 'warning'} showIcon message={discovery?.reason || '此指南未附带候选快照。请通过 GitHub 检索入口选择并核对任务，也可以记录人工选题。'} />
    {discovery && <Paragraph type="secondary" style={{ marginTop: 8 }}>本次采样 {discovery.sampled_count} 项，排除已负责、锁定或未开放项 {discovery.blocked_count} 项。快照取得时间：{sampledAt}（可能使用缓存）；操作前核对最新状态。</Paragraph>}
    {discovery?.candidates.map((c) => <Card key={c.number} size="small" style={{ marginTop: 10 }}>
      <a href={c.url} target="_blank" rel="noreferrer">#{c.number} {c.title}</a>
      <div style={{ marginTop: 6 }}><Tag>{c.origin === 'labelled' ? '标签候选，仍待核对' : '普通 issue，仅供浏览'}</Tag>{c.labels.map((label) => <Tag key={label}>{label}</Tag>)}</div>
      {c.checks.map((text, i) => <Paragraph key={i} style={{ marginBottom: 4 }}>{text}</Paragraph>)}
      <Button size="small" onClick={() => choose(c.url, c.title)}>填入待核对任务 #{c.number}</Button>
    </Card>)}
    <Space wrap style={{ marginTop: 12 }}>
      {(discovery?.search_links.length ? discovery.search_links : [{ label: '全部开放 issue', url: issuesUrl + '?q=is%3Aissue+is%3Aopen' }]).map((link) => <a key={link.url} href={link.url} target="_blank" rel="noreferrer">查看 {link.label}</a>)}
    </Space>
    <Paragraph style={{ marginTop: 10 }}>选题时先核对：能否复现、范围是否够小、是否已有负责人或对应 PR、维护者是否接受该类改动。没有 issue 时可人工选题，并在问题描述中记录具体来源和理由。</Paragraph>
    {field('task', '选定任务', '用一句话写清准备解决的问题')}
    {field('issueUrl', '任务 issue 链接（可选）', `${issuesUrl}/具体编号`)}
    {field('problem', '问题、范围与来源', '说明具体问题、复现方式及本次处理范围；人工选题请补充来源', true)}
    {stage === 'C' && <Paragraph type="secondary" style={{ marginTop: 10 }}>先记录上述任务信息；完成实际修改后，切到“首次 PR 路径”填写下面的验证记录和草稿。当前页面切换步骤会保留内容。</Paragraph>}
    <details open={stage === 'D'} style={{ marginTop: 12 }}>
      <summary style={{ cursor: 'pointer' }}>记录实际修改与验证</summary>
      {field('changeSummary', '已经做出的修改', '填写已经完成的改动及其如何解决问题；不要把计划写成完成结果', true)}
      {field('baseRevision', '改动基准提交（可选）', '填写实际修改前的完整 Git 提交 SHA，便于核对版本')}
      {field('files', '实际修改文件（每行一个仓库相对路径）', '例如 docs/example.rst；这里不预填或推测修改文件', true)}
      {field('patch', '实际 git diff（可选，仅本机解析）', '可粘贴 git diff 或 git diff --cached 输出，自动提取变更路径；提交前自行检查有无敏感信息', true)}
      {input.patch.trim() && <Paragraph>解析到的变更路径：{changedFiles(input).join('、') || '尚未识别，请核对 diff 格式'}</Paragraph>}
      <Paragraph style={{ marginTop: 12, marginBottom: 6 }}><Text strong>实际测试状态</Text></Paragraph>
      <Radio.Group aria-label="实际测试状态" value={input.testStatus} onChange={(e) => update('testStatus', e.target.value)} options={[{ label: '未运行', value: 'not_run' }, { label: '通过（用户记录）', value: 'passed' }, { label: '失败', value: 'failed' }]} />
      {input.testStatus !== 'not_run' && <>
        {field('testCommand', '实际测试命令', '填写实际运行的命令')}
        {field('testExitCode', '实际退出码', '通过为 0；失败填写实际非零退出码')}
        {field('testOutput', '实际结果与范围', '记录通过、失败、跳过数量和未验证范围，不要仅写“正常”', true)}
      </>}
      {problems.length > 0 && <Alert type="info" style={{ marginTop: 12 }} message="草稿还需要以下信息" description={<ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>} />}
      <Button type="primary" disabled={problems.length > 0} style={{ marginTop: 12 }} onClick={() => setDraft(buildContributionDraft(guide, input))}>整理本机 PR 草稿</Button>
    </details>
    {draft && <div style={{ marginTop: 12 }}>
      <Alert showIcon type={input.testStatus === 'passed' ? 'info' : 'warning'} message="草稿已整理，待人工审阅；尚未提交" />
      <Input.TextArea aria-label="PR 草稿预览" value={draft} readOnly rows={12} style={{ marginTop: 10 }} />
      <Space wrap style={{ marginTop: 10 }}><Typography.Text copyable={{ text: draft }}>复制草稿</Typography.Text><Button onClick={download}>下载 PR 草稿 Markdown</Button></Space>
    </div>}
  </Card>
}
