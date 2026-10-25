import { useState } from 'react'
import { Alert, Button, Card, Input, Radio, Space, Tag, Typography, Upload, message } from 'antd'
import type { Guide } from '../../types/guide'
import { buildContributionDraft, changedFiles, contributionProblems, contributionPreparationJson, parseContributionPreparation, referencedExecutions, taskExplorationEntries, type ContributionInput, type ContributionPreparation } from '../../types/contribution'
import { useContributionSession } from '../../types/contributionSession'
import { learningReferences, taskDirections } from '../../types/noviceGuidance'
import type { LearningRecord } from '../../types/learningProgress'

const { Paragraph, Text } = Typography

export default function ContributionWorkbench({ guide, stage, records = {}, onExploreStep }: { guide: Guide; stage: string; records?: Record<string, LearningRecord>; onExploreStep?: (id: number) => void }) {
  const { session, updateSession } = useContributionSession(guide)
  const { input, draft, referenceRevision: preparationRevision } = session
  const setInput = (value: ContributionInput | ((old: ContributionInput) => ContributionInput)) => updateSession(s => ({ ...s, input: typeof value === 'function' ? value(s.input) : value }))
  const setDraft = (value: string) => updateSession(s => ({ ...s, draft: value }))
  const setPreparationRevision = (value: string) => updateSession(s => ({ ...s, referenceRevision: value }))
  const [pendingImport, setPendingImport] = useState<ContributionPreparation | null>(null)
  const [importError, setImportError] = useState('')
  const [restored, setRestored] = useState(false)
  const discovery = guide.issue_discovery
  const sampledAt = discovery?.sampled_at && Number.isFinite(Date.parse(discovery.sampled_at))
    ? new Date(discovery.sampled_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + '（北京时间）' : '未记录'
  const issuesUrl = guide.repo_url + '/issues'
  const update = <K extends keyof ContributionInput>(key: K, value: ContributionInput[K]) => {
    setInput((s) => ({ ...s, [key]: value }))
    setDraft('')
  }
  const problems = contributionProblems(guide, input)
  const hasPreparation = Object.entries(input).some(([key, value]) => key === 'testStatus' ? value !== 'not_run' : key === 'kind' ? value !== 'unspecified' : value.trim())
  const referenceText = referencedExecutions(guide, records)
  const exploration = taskExplorationEntries(guide, input.kind)
  const choose = (url: string, title: string) => {
    setInput((s) => ({ ...s, issueUrl: url, task: title }))
    setDraft('')
  }
  const field = (key: keyof ContributionInput, label: string, placeholder: string, multiline = false) => <label style={{ display: 'block', marginTop: 12 }}>
    <Text strong>{label}</Text>
    {multiline ? <Input.TextArea aria-label={label} rows={3} maxLength={key === 'patch' ? 1_000_000 : key === 'verificationNotes' ? 100_000 : 10000} value={input[key]} placeholder={placeholder} onChange={(e) => update(key, e.target.value as never)} />
      : <Input aria-label={label} value={input[key]} maxLength={1000} placeholder={placeholder} onChange={(e) => update(key, e.target.value as never)} />}
  </label>
  const download = () => {
    const url = URL.createObjectURL(new Blob([draft], { type: 'text/markdown;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url; a.download = `OpenGuide-${guide.owner}-${guide.repo}-pr-draft.md`; a.click(); URL.revokeObjectURL(url)
  }
  const downloadPreparation = () => {
    try {
      const raw = contributionPreparationJson(guide, input, preparationRevision)
      const url = URL.createObjectURL(new Blob([raw], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url; link.download = `OpenGuide-${guide.owner}-${guide.repo}-preparation.json`; link.click(); URL.revokeObjectURL(url)
    } catch (error) { void message.error(error instanceof Error ? error.message : '准备记录导出失败') }
  }
  if (stage !== 'C' && stage !== 'D') return null
  return <Card title="贡献工作台：任务 → 改动 → PR 草稿" style={{ marginTop: 16 }}>
    <Paragraph type="secondary">表单与草稿保留在本页内存，切换步骤或重新生成同一仓库版本可继续编辑；刷新或关闭页面前请先导出。不同仓库和参考版本分别保留，不自动混用。内容不会发给模型或提交到 GitHub，导出前检查敏感信息。</Paragraph>
    <Space wrap style={{ marginBottom: 12 }}>
      <Button disabled={!hasPreparation} onClick={downloadPreparation}>导出准备记录 JSON</Button>
      <Upload accept=".json" showUploadList={false} beforeUpload={async (file) => {
        setImportError(''); setPendingImport(null)
        try {
          if (file.size > 2_000_000) throw new Error('准备记录不能超过 2 MB')
          setPendingImport(parseContributionPreparation(await file.text(), guide))
        } catch (error) { setImportError(error instanceof Error ? error.message : '准备记录读取失败') }
        return false
      }}><Button>从准备记录恢复</Button></Upload>
    </Space>
    {importError && <Alert type="error" showIcon message="未导入，当前表单保持原样" description={importError} style={{ marginBottom: 12 }} />}
    {pendingImport && <Alert type="info" showIcon message="准备记录已读取，尚未替换表单" style={{ marginBottom: 12, overflowWrap: 'anywhere' }}
      description={<>
        <Paragraph>任务：{pendingImport.input.task || '尚未填写'}；参考版本：{pendingImport.referenceRevision}；测试状态：{pendingImport.input.testStatus === 'not_run' ? '未运行' : pendingImport.input.testStatus === 'failed' ? '用户记录失败' : '用户记录通过（未核验）'}。</Paragraph>
        <Paragraph>恢复将替换本页表单，当前内容请先导出。{pendingImport.referenceRevision !== guide.default_branch ? '文件参考版本与当前指南不同，恢复后需重新核对规范与验证要求。' : ''}</Paragraph>
        <Space wrap><Button onClick={() => {
          setInput(pendingImport.input); setPreparationRevision(pendingImport.referenceRevision); setDraft(''); setRestored(true); setPendingImport(null)
        }}>使用该记录替换表单</Button><Button onClick={() => setPendingImport(null)}>取消导入</Button></Space>
      </>} />}
    {restored && <Paragraph type="secondary">已恢复本机准备记录，尚未提交或独立核验；PR 草稿需补齐实际改动后重新整理。</Paragraph>}
    {preparationRevision !== guide.default_branch && <Alert type="warning" showIcon message="准备记录与当前指南版本不同" description={`文件记录：${preparationRevision}；当前指南：${guide.default_branch}。提交前核对贡献规范与验证要求。`} style={{ marginBottom: 12, overflowWrap: 'anywhere' }} />}
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
    <Text strong>任务准备卡 · 从一个具体问题开始</Text>
    <div style={{ marginTop: 8 }}>
      <label>贡献方向<select aria-label="贡献方向" value={input.kind} style={{ display: 'block', padding: 8, maxWidth: '100%' }} onChange={e => update('kind', e.target.value as ContributionInput['kind'])}>
        <option value="unspecified">先选择探索方向（可稍后补充）</option>
        {Object.entries(taskDirections).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
      </select></label>
      {input.kind !== 'unspecified' && <details style={{ marginTop: 10 }}>
        <summary style={{ cursor: 'pointer' }}>查看此方向的行动建议 · 仍需实际核对</summary>
        <Alert showIcon type="info" style={{ marginTop: 8 }} message="先取得自己的观察与依据"
          description={<><Paragraph>{taskDirections[input.kind].start}</Paragraph><Paragraph style={{ marginBottom: 0 }}>{taskDirections[input.kind].check}</Paragraph></>} />
      </details>}
    </div>
    {exploration.length > 0 && <details style={{ marginTop: 12 }}>
      <summary style={{ cursor: 'pointer' }}>当前仓库的探索起点 · {exploration.length} 个原文入口</summary>
      <Paragraph type="secondary" style={{ marginTop: 8 }}>从已取得的具体说明或测试入口开始观察；这些入口不证明存在缺陷、测试缺口或可认领任务。</Paragraph>
      {exploration.map(entry => <Card key={entry.stepId} size="small" style={{ marginTop: 8 }}>
        <a href={entry.href} target="_blank" rel="noreferrer">{entry.source} ↗</a>
        {entry.command && <><Paragraph style={{ marginTop: 6, marginBottom: 4 }}>步骤 {entry.stepId} · 执行位置：{entry.directory === '.' ? '仓库根目录' : entry.directory || '待核对'}</Paragraph>
          <Paragraph copyable={{ text: entry.command }} style={{ overflowWrap: 'anywhere' }}><Text code>{entry.command}</Text></Paragraph></>}
        {onExploreStep && <Button size="small" onClick={() => onExploreStep(entry.stepId)}>查看本步前置条件与检查方法</Button>}
      </Card>)}
    </details>}
    <details style={{ marginTop: 12 }}>
      <summary style={{ cursor: 'pointer' }}>新手行动清单与参考文章 · 通用方法</summary>
      <ol>
        <li>先阅读 README、贡献说明和参与政策，搜索相同问题与已有 PR；需讨论时先确认处理范围。</li>
        <li>在原始版本记录实际观察，区分已有问题与本次修改引入的问题；只选择一个可说明的小目标。</li>
        <li>按仓库规则准备自己的 Fork 或开发分支；检查实际差异，再记录修改后的验证结果。</li>
        <li>提交后关注项目要求的检查和审阅意见，修改时更新原有工作分支，并重新验证受影响的内容。</li>
      </ol>
      <Paragraph type="secondary">以下是学习参考，不代表当前仓库的专属要求。各项目的测试、签署或提交规则需另行核对。</Paragraph>
      {learningReferences.map(r => <Paragraph key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a></Paragraph>)}
      <a href="https://github.com/firstcontributions/first-contributions" target="_blank" rel="noreferrer">Git 流程还不熟悉：First Contributions 练习项目 ↗</a>
      <Paragraph type="secondary">练习项目用于熟悉流程，不等同已经为当前仓库作出实际贡献。</Paragraph>
    </details>
    {field('task', '选定任务', '用一句话写清准备解决的问题')}
    {field('issueUrl', '任务 issue 链接（可选）', `${issuesUrl}/具体编号`)}
    {field('problem', '问题、范围与来源', '说明具体问题、复现方式及本次处理范围；人工选题请补充来源', true)}
    {field('acceptance', '验收标准（计划）', '怎样检查这个小目标已经达到？计划不等于实际验证结果', true)}
    {field('outOfScope', '本次不处理的范围（可选）', '例如：仅修复这一个组件，不扩大到其他功能')}
    <details style={{ marginTop: 12 }}>
      <summary style={{ cursor: 'pointer' }}>记录修改前观察与指南执行记录</summary>
      {field('baselineNotes', '修改前实际观察', '填写原始版本、复现步骤、预期与实际现象；没有复现时如实记录', true)}
      <Button size="small" style={{ marginTop: 10 }} disabled={!referenceText} onClick={() => {
        const next = input.verificationNotes.includes(referenceText) ? input.verificationNotes : [input.verificationNotes, referenceText].filter(Boolean).join('\n\n')
        if (next.length > 100_000) { void message.warning('执行记录过长，请先导出学习记录，再手工引用相关部分。'); return }
        update('verificationNotes', next)
      }}>引用指南执行记录作为基线</Button>
      <Paragraph type="secondary" style={{ marginTop: 8 }}>{referenceText ? '仅引用用户已填写的记录，不会把浏览完成或建议命令视为执行成功，也不会替你填写修改后的测试状态。' : '尚无可引用的执行记录；先在相应步骤填写实际执行情况。仅点击“已核对”不会产生执行记录。'}</Paragraph>
      {field('verificationNotes', '引用的指南执行记录（用户记录，待核对）', '引用记录只作基线或定位参考，不能代替本次修改后的验证', true)}
    </details>
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
        {field('testDirectory', '实际测试目录', '填写本次改动后实际运行检查的目录')}
        {field('testScope', '实际验证范围', '例如：后端相关单元测试；未验证前端与完整 CI')}
        {field('testExitCode', '实际退出码', '通过为 0；失败填写实际非零退出码')}
        {field('testOutput', '实际结果与范围', '记录通过、失败、跳过数量和未验证范围，不要仅写“正常”', true)}
      </>}
      {problems.length > 0 && <Alert type="info" style={{ marginTop: 12 }} message="草稿还需要以下信息" description={<ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>} />}
      <Button type="primary" disabled={problems.length > 0} style={{ marginTop: 12 }} onClick={() => setDraft(buildContributionDraft(guide, input, preparationRevision))}>整理本机 PR 草稿</Button>
    </details>
    {draft && <div style={{ marginTop: 12 }}>
      <Alert showIcon type={input.testStatus === 'passed' ? 'info' : 'warning'} message="草稿已整理，待人工审阅；尚未提交" />
      <Input.TextArea aria-label="PR 草稿预览" value={draft} readOnly rows={12} style={{ marginTop: 10 }} />
      <Space wrap style={{ marginTop: 10 }}><Typography.Text copyable={{ text: draft }}>复制草稿</Typography.Text><Button onClick={download}>下载 PR 草稿 Markdown</Button></Space>
    </div>}
  </Card>
}
