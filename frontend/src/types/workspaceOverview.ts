import type { Guide } from './guide'
import type { Profile } from './profile'

export function workspaceOverview({ loading, demo, profile, guide, url }: {
  loading: boolean; demo: boolean; profile: Profile | null; guide: Guide | null; url: string
}) {
  const rawUrl = loading ? url : guide?.repo_url || (profile && !demo ? `https://github.com/${profile.owner}/${profile.repo}` : url)
  const match = rawUrl.trim().match(/^(?:https:\/\/github\.com\/)?([\w.-]+\/[\w.-]+?)(?:\.git)?\/?$/)
  const repository = match?.[1] || '正在连接仓库'
  if (loading) return { repository, status: '正在读取仓库概况', description: '正在获取仓库的基本信息、语言与文档入口。', facts: [] as string[], tone: 'loading' }
  // Never present cached/sample metadata as live collection, or combine an
  // imported guide with a previous repository's profile.
  if (guide) return { repository, status: '已载入离线指南', description: '沿着已保存的步骤继续探索；本次没有重新联网核验资料。',
    facts: ['本机记录', `引用版本 ${guide.default_branch.slice(0, 12)}`], tone: 'saved' }
  if (demo) return { repository, status: '正在浏览交互示例', description: '指南与体检是静态示例，贡献问答会另外读取仓库资料。', facts: ['示例浏览'], tone: 'demo' }
  if (!profile) return { repository, status: '等待仓库资料', description: '读取仓库后，概况与资料入口会显示在这里。', facts: [] as string[], tone: 'idle' }
  const unavailable = new Set(profile?.unavailable_signals ?? [])
  const facts = [] as string[]
  if (profile?.default_branch) facts.push(`默认分支 ${profile.default_branch}`)
  if (profile && !unavailable.has('languages')) {
    const languages = Object.entries(profile.languages).sort((a,b) => b[1]-a[1]).slice(0,2).map(([name]) => name)
    if (languages.length) facts.push(languages.join(' · '))
  }
  if (profile?.has_readme && !unavailable.has('root')) facts.push('README 入口')
  return { repository, status: unavailable.size ? '仓库概况已取得 · 部分信息待确认' : '仓库概况已取得',
    description: profile?.description || '先读懂环境与测试入口，再选择一个范围明确的小任务。', facts, tone: unavailable.size ? 'partial' : 'ready' }
}
