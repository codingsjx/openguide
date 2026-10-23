import { useState } from 'react'
import { Alert, Button, Tabs, Input, Space, message, Upload } from 'antd'
import {
  GithubOutlined,
  QuestionCircleOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  ArrowRightOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
  ApartmentOutlined,
  UploadOutlined,
  LinkOutlined,
} from '@ant-design/icons'

import { api } from '../api/client'
import type { Profile } from '../types/profile'
import ProfileCard from '../components/ProfileCard'
import GuideGenerator from '../components/GuideGenerator'
import LlmSettings from '../components/LlmSettings'
import RepoAskPage from './RepoAskPage'
import GuideWizard from '../components/GuideWizard'
import type { Guide } from '../types/guide'
import { parseSavedGuide } from '../types/savedGuide'
import LandingJourney from '../components/LandingJourney'
import WorkspaceHero from '../components/WorkspaceHero'
import { lastLearningGuide } from '../types/learningProgress'

const DEMO_URL = 'https://github.com/psf/requests'

const demoProfile: Profile = {
  owner: 'psf',
  repo: 'requests',
  html_url: DEMO_URL,
  description: 'A simple, yet elegant, HTTP library for Python.',
  stars: 0,
  forks: 0,
  open_issues: 0,
  languages: { Python: 0.86, JavaScript: 0.08, Shell: 0.04, Makefile: 0.02 },
  license: 'Apache-2.0',
  default_branch: 'main',
  has_readme: true,
  has_contributing: true,
  has_docs: true,
  build: { tool: 'pyproject.toml', package_manager: 'pip', test_cmd: 'pytest', has_makefile: true, has_dockerfile: false },
  gfi: { count: 0, oldest_days: null },
  activity: { commits_30d: 0, last_release_days: null },
  suitability: 'promising',
  reasons: ['文档入口清晰，贡献约定完整', '存在适合新手的 issue 信号', '测试命令和开发依赖可以被识别'],
}

const demoGuide: Guide = {
  repo_url: DEMO_URL, owner: 'psf', repo: 'requests', default_branch: 'main',
  unsuitable: false, reasons: [], generation_mode: 'heuristic', is_demo: true,
  warnings: ['静态交互示例，不代表对当前仓库的实时分析；请正式分析后核对原文。'],
  steps: (['A', 'B', 'C', 'D'] as const).map((stage, i) => ({
    step_id: i + 1, stage,
    stage_label: ['环境搭建', '测试基线', '挑选 issue', '首次 PR 路径'][i],
    title: ['确认开发环境与安装方式', '确认最小测试路径', '核对任务当前状态', '阅读贡献约定并准备 PR'][i],
    command: null, expected: '正式分析后，根据仓库原文确认操作与成功标准。',
    fail_hints: [], evidence: { kind: 'missing', source: '', quote: '' },
  })),
}

export default function HomePage() {
  const [url, setUrl] = useState('')
  const [tab, setTab] = useState<string>('guide')
  const [loading, setLoading] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [submittedUrl, setSubmittedUrl] = useState('')
  const [demoMode, setDemoMode] = useState(false)
  const [savedGuide, setSavedGuide] = useState<Guide | null>(null)
  const [guideVersion, setGuideVersion] = useState(0)
  const [useAiGuide, setUseAiGuide] = useState(true)
  const [submittedUseLlm, setSubmittedUseLlm] = useState(true)
  const [resumeGuide] = useState<Guide | null>(() => {
    try {
      const raw = lastLearningGuide(window.localStorage)
      return raw ? parseSavedGuide(raw) : null
    } catch { return null }
  })

  async function handleSubmit() {
    const trimmed = url.trim()
    if (!trimmed) return
    if (loading) return
    setProfileError(null)
    setLoading(true)
    setSubmittedUseLlm(useAiGuide)
    setSavedGuide(null)
    setDemoMode(false)
    setTab('guide')
    setProfile(null)
    setSubmittedUrl('')
    try {
      const p = await api.postProfile(trimmed)
      setProfile(p)
      setSubmittedUrl(trimmed)
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : '仓库读取失败，请重试或导入已保存指南。')
    } finally {
      setLoading(false)
    }
  }

  function startDemo() {
    setGuideVersion((version) => version + 1)
    setSavedGuide(null)
    setUrl(DEMO_URL)
    setProfile(demoProfile)
    setSubmittedUrl(DEMO_URL)
    setDemoMode(true)
    setTab('guide')
  }

  const showGuide = Boolean(savedGuide || (profile && submittedUrl))
  const workspaceUrl = savedGuide?.repo_url || (profile ? `https://github.com/${profile.owner}/${profile.repo}` : '')

  return (
    <div className={`app-shell${showGuide ? ' has-workspace' : ''}`}>
      <a className="skip-link" href="#start">跳到仓库输入</a>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#start" aria-label="OpenGuide，前往仓库输入"><span className="brand-mark"><ApartmentOutlined /></span><span>OpenGuide<span className="brand-caption">开源贡献，从容开始</span></span></a>
          <div className="topbar-actions"><a className="github-link" href="https://github.com/codingsjx/openguide" target="_blank" rel="noreferrer" aria-label="在 GitHub 查看 OpenGuide 源码"><GithubOutlined /><span>GitHub</span></a><LlmSettings /></div>
        </div>
      </header>

      <main>
      <div className="page-wrap">
        {!showGuide && !loading ? <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-dot" />让第一次开源贡献，有路可循</div>
            <h1 id="hero-title">从读懂仓库，<br />到你的<span>第一个 PR<span className="headline-dot">.</span></span></h1>
            <p className="hero-description">把陌生的项目，拆成清晰的下一步。<br />找到环境、测试和贡献入口，带着原文依据开始行动。</p>
            <div className="trust-row"><span><CheckCircleOutlined /> 分步贡献路线</span><span><LinkOutlined /> 原文证据可查</span><span><QuestionCircleOutlined /> 随时继续追问</span></div>
          </div>
          <LandingJourney />
        </section> : <WorkspaceHero loading={loading} demo={demoMode} profile={profile} guide={savedGuide}
          url={loading ? url : workspaceUrl} tab={tab} onViewChange={setTab} />}

        <section className="search-panel" id="start" aria-labelledby="search-title" aria-busy={loading}>
          <div className="panel-heading"><div><span className="section-kicker">{showGuide ? 'REPOSITORY' : 'START YOUR JOURNEY'}</span><h2 id="search-title">{showGuide ? '当前探索的仓库' : '你的第一站，是哪个仓库？'}</h2></div><span className="search-panel-hint"><GithubOutlined /> GitHub 公开仓库</span></div>
          <Space.Compact className="search-box">
            <Input aria-label="GitHub 仓库地址" size="large" placeholder="https://github.com/owner/repo" value={url} onChange={(e) => setUrl(e.target.value)} onPressEnter={handleSubmit} disabled={loading} prefix={<GithubOutlined />} />
            <Button type="primary" size="large" icon={<RocketOutlined />} loading={loading} onClick={handleSubmit}>生成路线图 <ArrowRightOutlined /></Button>
          </Space.Compact>
          <label style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginTop: 12, color: '#4c6662' }}>
            生成方式
            <select aria-label="首次指南生成方式" disabled={loading} value={useAiGuide ? 'ai' : 'rules'} onChange={(event) => setUseAiGuide(event.target.value === 'ai')}
              style={{ maxWidth: '100%', padding: '5px 8px', border: '1px solid #cfddd9', borderRadius: 6, color: '#244d45', background: '#fff' }}>
              <option value="ai">AI 生成 · 可能需要较长等待</option>
              <option value="rules">快速原文整理 · 不调用模型</option>
            </select>
          </label>
          {profileError && <Alert showIcon type="error" message="仓库读取失败" description={profileError} style={{ marginTop: 12 }} />}
          {!showGuide && !loading && resumeGuide && <Alert type="info" showIcon style={{ marginTop: 12 }}
            message={`继续上次指南：${resumeGuide.owner}/${resumeGuide.repo}`}
            description="从本机快照和学习记录继续，不重新请求模型或核验仓库；贡献工作台表单和问答历史不在此快照中。"
            action={<Button onClick={() => {
              setProfile(null); setProfileError(null); setSavedGuide(resumeGuide); setGuideVersion((version) => version + 1)
              setSubmittedUrl(resumeGuide.repo_url); setUrl(resumeGuide.repo_url); setDemoMode(false); setTab('guide')
            }}>继续上次指南</Button>} />}
          <div className="search-foot"><div className="search-example"><span>先看看怎么用</span><button onClick={startDemo} disabled={loading}>体验 requests 示例 <ArrowRightOutlined /></button></div><span className="search-separator" /><Upload accept=".json" showUploadList={false} beforeUpload={async (file) => {
            try {
              if (file.size > 2_000_000) throw new Error('指南文件不能超过 2 MB')
              const imported = parseSavedGuide(await file.text())
              setSavedGuide(imported)
              setGuideVersion((version) => version + 1)
              setSubmittedUrl(imported.repo_url)
              setUrl(imported.repo_url)
              setDemoMode(false)
              setTab('guide')
            } catch (error) { void message.error(error instanceof Error ? error.message : '导入失败') }
            return false
          }}><Button type="text" icon={<UploadOutlined />} disabled={loading}>导入已保存指南<span className="import-caption"> · 离线查看</span></Button></Upload><span className="shortcut">Enter ↵</span></div>
        </section>

        {!showGuide && !loading && <section className="how-it-works" id="how-it-works" aria-labelledby="how-title"><div className="feature-heading"><div><span className="section-kicker">A CLEARER WAY TO CONTRIBUTE</span><h2 id="how-title">不用一次读懂整个项目</h2></div><p>先找到起点，再走好每一步。</p></div><div className="feature-grid">
          <article><div className="feature-top"><span className="feature-icon"><FileSearchOutlined /></span><span className="feature-number">01</span></div><h3>先了解，是否适合你</h3><p>查看仓库语言、构建方式与任务线索，识别上手前需要确认的信息。</p><a className="feature-link" href="#start">仓库体检 <ArrowRightOutlined /></a></article>
          <article><div className="feature-top"><span className="feature-icon"><RocketOutlined /></span><span className="feature-number">02</span></div><h3>把大目标，拆成小步骤</h3><p>从环境搭建、测试到选题与 PR，按阶段查看操作入口和前置条件。</p><a className="feature-link" href="#start">贡献指南 <ArrowRightOutlined /></a></article>
          <article><div className="feature-top"><span className="feature-icon"><LinkOutlined /></span><span className="feature-number">03</span></div><h3>有疑问，就回到原文</h3><p>展开出处、核对建议，也可以围绕当前仓库追问。资料不足时会明确说明。</p><a className="feature-link" href="#start">证据与问答 <ArrowRightOutlined /></a></article>
        </div></section>}
      </div>

      {showGuide && (
        <section className="results-wrap" id="workspace" aria-label="仓库贡献工作台">
        <div className="workspace-heading"><div><span className="workspace-indicator" /><span>{savedGuide ? '已保存指南' : demoMode ? '交互示例' : '贡献工作区'}</span></div><a href={workspaceUrl} target="_blank" rel="noreferrer"><GithubOutlined /> {workspaceUrl.replace('https://github.com/', '')} <ArrowRightOutlined /></a></div>
        {demoMode && <div className="demo-banner"><ThunderboltOutlined /><span>当前指南与体检为静态 requests 示例。点击「生成路线图」分析所填仓库；贡献问答会单独读取仓库资料。</span></div>}
        <Tabs
          activeKey={tab}
          onChange={setTab}
          className="results-tabs"
          items={[
            {
              key: 'guide',
              label: (
                <Space>
                  <ThunderboltOutlined /> 贡献指南
                </Space>
              ),
              children: savedGuide ? <GuideWizard key={`saved-${guideVersion}`} guide={savedGuide} url={savedGuide.repo_url} /> : demoMode ? <GuideWizard key={`demo-${guideVersion}`} guide={demoGuide} url={submittedUrl} /> : <GuideGenerator initialUrl={submittedUrl} initialUseLlm={submittedUseLlm} />,
            },
            {
              key: 'health',
              disabled: Boolean(savedGuide),
              label: (
                <Space>
                  <RocketOutlined /> 仓库体检
                </Space>
              ),
              children: profile ? <ProfileCard profile={profile} /> : null,
            },
            {
              key: 'ask',
              disabled: Boolean(savedGuide),
              label: (
                <Space>
                  <QuestionCircleOutlined /> 贡献问答
                </Space>
              ),
              children: <RepoAskPage initialUrl={submittedUrl} />,
            },
          ]}
        />
        </section>
      )}
      </main>
      <footer className="site-footer"><div><a href="#start" className="footer-brand"><ApartmentOutlined /> OpenGuide</a><span>让开源的第一步，更清晰一点。</span></div><div><span><SafetyCertificateOutlined /> 核对原文，再开始行动</span><a href="https://github.com/codingsjx/openguide#readme" target="_blank" rel="noreferrer">项目说明 <ArrowRightOutlined /></a></div></footer>
    </div>
  )
}
