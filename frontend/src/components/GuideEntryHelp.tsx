import { Card, Typography } from 'antd'
import type { Guide } from '../types/guide'

const { Paragraph, Text } = Typography

export default function GuideEntryHelp({ guide, stage, expanded }: { guide: Guide; stage: string; expanded: boolean }) {
  if (stage !== 'A' && stage !== 'D') return null
  const safeName = /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/
  const repoUrl = safeName.test(guide.owner) && safeName.test(guide.repo)
    ? `https://github.com/${guide.owner}/${guide.repo}` : undefined
  return <Card size="small" style={{ marginTop: 12 }}>
    <details open={expanded}>
      <summary style={{ cursor: 'pointer' }}>{stage === 'A' ? '通用 Git 起步与环境准备' : '通用 PR 准备清单'} · 工具提供</summary>
      <Paragraph type="secondary" style={{ marginTop: 10 }}>以下是工具提供的通用操作提示，不是仓库原文要求，尚未执行。仓库特殊安装方式、参与政策和提交规范仍以最新原文为准。</Paragraph>
      {stage === 'A' ? <ol>
        <li>先确认本机已安装 Git。选择一个用于存放项目的目录；已有仓库副本时先核对版本，避免重复克隆或覆盖文件。</li>
        <li>没有本地副本时，可从仓库 Code 菜单复制地址，或参考下面根据当前仓库地址组成的标准 Git 命令。
          {repoUrl && <Paragraph copyable={{ text: `git clone ${repoUrl}.git` }} style={{ marginTop: 8, overflowWrap: 'anywhere' }}><Text code>{`git clone ${repoUrl}.git`}</Text></Paragraph>}
          <Paragraph type="secondary">在你选择的存放目录运行；完成后进入新建的仓库目录，再按各步骤标注的子目录操作。命令会联网下载仓库，本工具没有代为执行。</Paragraph>
        </li>
        <li>核对下方带出处的运行时版本与工具要求，分别准备各组件环境；缺少安装说明时先查看原文链接。仓库有子模块或大文件时，还需核对其专门的获取要求。</li>
        <li>安装依赖后再运行对应组件的检查；只有实际运行并核对结果后才标记步骤完成。</li>
      </ol> : <ol>
        <li>确认任务仍需处理，写清问题、改动范围与验收方法；先查维护者是否要求讨论、认领或限制 AI 协助。</li>
        <li>核对仓库 Fork、分支和提交规范，在自己的开发分支进行实际修改。尚未修改时先保留任务记录。</li>
        <li>检查实际 diff，按指南及仓库要求运行检查，记录退出码、失败、跳过与未验证范围。</li>
        <li>在下面的贡献工作台填写真实改动与验证记录，导出草稿。人工核对模板、敏感信息及 AI 协助披露后，再通过 GitHub 发起 PR。</li>
      </ol>}
      {repoUrl && <a href={stage === 'A' ? repoUrl : repoUrl + '/compare'} target="_blank" rel="noreferrer">{stage === 'A' ? '打开仓库核对获取说明 ↗' : '打开 GitHub 比较页面（不会自动提交）↗'}</a>}
    </details>
  </Card>
}
