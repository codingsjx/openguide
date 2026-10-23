import { useState } from 'react'
import { ArrowRightOutlined, BranchesOutlined, CodeOutlined, FileTextOutlined, GithubOutlined, PauseOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { Profile } from '../types/profile'
import type { Guide } from '../types/guide'
import { workspaceOverview } from '../types/workspaceOverview'

export default function WorkspaceHero({ loading, demo, profile, guide, url, tab, onViewChange }: {
  loading: boolean; demo: boolean; profile: Profile | null; guide: Guide | null; url: string; tab: string; onViewChange: (view: string) => void
}) {
  const [paused, setPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const overview = workspaceOverview({ loading, demo, profile, guide, url })
  const viewName = tab === 'health' ? '仓库体检' : tab === 'ask' ? '贡献问答' : '贡献指南'
  return <section className={`explorer-hero tone-${overview.tone}${paused ? ' motion-paused' : ''}`} aria-label="仓库探索动态概览" aria-busy={loading}>
    <div className="explorer-copy">
      <span className="section-kicker">YOUR OPEN SOURCE JOURNEY</span>
      <h1>{loading ? '让陌生的仓库，慢慢变清晰' : '从理解项目，到开始贡献'}</h1>
      <div className="explorer-repository"><GithubOutlined /><strong>{overview.repository}</strong></div>
      <p className="explorer-description">{overview.description}</p>
      <div className="explorer-facts">{overview.facts.map((fact) => <span key={fact}>{fact}</span>)}</div>
      <div className="explorer-actions">
        <span className="explorer-live-status" role="status" aria-live="polite"><i />{overview.status}</span>
        {!loading && <a href="#workspace" onClick={() => onViewChange('guide')}>查看贡献指南 <ArrowRightOutlined /></a>}
      </div>
    </div>
    <div className="explorer-visual">
      <div className="explorer-visual-heading"><span>{loading ? '正在连接仓库资料' : `当前查看 · ${viewName}`}</span>
        <button type="button" className="motion-toggle" onClick={() => setPaused((value) => !value)} aria-pressed={paused} aria-label={paused ? '播放动态装饰' : '暂停动态装饰'}>
          {paused ? <PlayCircleOutlined /> : <PauseOutlined />}{paused ? '播放动效' : '暂停动效'}
        </button>
      </div>
      <div className="explorer-network" aria-hidden="true">
        <div className="network-orbit orbit-outer" /><div className="network-orbit orbit-inner" />
        <div className="network-rail rail-left" /><div className="network-rail rail-right" />
        <div className="network-hub"><GithubOutlined /><span>仓库资料</span></div>
        <div className="network-file file-readme"><FileTextOutlined /><span>项目说明</span><i /></div>
        <div className="network-file file-build"><CodeOutlined /><span>构建与测试</span><i /></div>
        <div className="network-file file-contribute"><BranchesOutlined /><span>贡献约定</span><i /></div>
        <span className="network-particle particle-one" /><span className="network-particle particle-two" />
      </div>
      <div className="explorer-route" aria-label="环境、测试、选题、PR，贡献路径示意">
        {['环境', '测试', '选题', 'PR'].map((stage, index) => <span key={stage}><b>{'ABCD'[index]}</b>{stage}{index < 3 && <ArrowRightOutlined />}</span>)}
        <em>路径示意</em>
      </div>
    </div>
  </section>
}
