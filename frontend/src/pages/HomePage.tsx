import { useState } from 'react'
import { Button, Tabs, Input, Space, Typography, message, Tag } from 'antd'
import {
  GithubOutlined,
  QuestionCircleOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  ArrowRightOutlined,
  SafetyCertificateOutlined,
  CodeOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'

import { api, ApiError } from '../api/client'
import type { Profile } from '../types/profile'
import ProfileCard from '../components/ProfileCard'
import GuideGenerator from '../components/GuideGenerator'
import LlmSettings from '../components/LlmSettings'
import GuidePage from './GuidePage'
import GuideWizard from '../components/GuideWizard'
import type { Guide } from '../types/guide'

const { Title, Paragraph } = Typography

const DEMO_URL = 'https://github.com/psf/requests'

const demoProfile: Profile = {
  owner: 'psf',
  repo: 'requests',
  html_url: DEMO_URL,
  description: 'A simple, yet elegant, HTTP library for Python.',
  stars: 53500,
  forks: 9300,
  open_issues: 210,
  languages: { Python: 0.86, JavaScript: 0.08, Shell: 0.04, Makefile: 0.02 },
  license: 'Apache-2.0',
  default_branch: 'main',
  has_readme: true,
  has_contributing: true,
  has_docs: true,
  build: { tool: 'pyproject.toml', package_manager: 'pip', test_cmd: 'pytest', has_makefile: true, has_dockerfile: false },
  gfi: { count: 6, oldest_days: 12 },
  activity: { commits_30d: 41, last_release_days: 18 },
  suitability: 'promising',
  reasons: ['文档入口清晰，贡献约定完整', '存在适合新手的 issue 信号', '测试命令和开发依赖可以被识别'],
}

const demoGuide: Guide = {
  repo_url: DEMO_URL,
  owner: 'psf',
  repo: 'requests',
  default_branch: 'main',
  unsuitable: false,
  reasons: [],
  steps: [
    { step_id: 1, stage: 'A', stage_label: '环境搭建', title: '创建开发环境并安装依赖', command: 'python -m venv .venv\nsource .venv/bin/activate\npip install -e ".[test]"', expected: '依赖安装完成，没有红色错误信息。', fail_hints: ['Windows 用户请使用 .venv\\Scripts\\activate。'], evidence: { kind: 'file', source: 'CONTRIBUTING.md#L22', quote: 'Install the development dependencies before running tests.' } },
    { step_id: 2, stage: 'B', stage_label: '测试基线', title: '跑通完整测试套件', command: 'pytest', expected: '终端显示测试全部通过，记录基线耗时。', fail_hints: ['先确认当前 Python 版本和虚拟环境是否正确。'], evidence: { kind: 'file', source: 'README.md#L86', quote: 'Run pytest to execute the test suite.' } },
    { step_id: 3, stage: 'C', stage_label: '挑选 issue', title: '从 good first issue 中选择任务', command: null, expected: '找到一个范围明确、已有复现方式的 issue。', fail_hints: ['优先选择可以在一个文件内完成的文档或测试改进。'], evidence: { kind: 'issue', source: '#1234', quote: 'A small, well-scoped issue is recommended for first-time contributors.' } },
    { step_id: 4, stage: 'D', stage_label: '首次 PR 路径', title: '创建分支并提交首个 PR', command: 'git checkout -b docs/first-contribution\ngit add .\ngit commit -m "docs: improve contribution guide"', expected: '分支推送成功，并在 GitHub 页面打开 PR。', fail_hints: ['提交前再次运行测试，并检查 PR 模板中的清单。'], evidence: { kind: 'file', source: 'CONTRIBUTING.md#L64', quote: 'Open a pull request with a clear description and test results.' } },
  ],
}

export default function HomePage() {
  const [url, setUrl] = useState('')
  const [tab, setTab] = useState<string>('guide')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [submittedUrl, setSubmittedUrl] = useState('')
  const [demoMode, setDemoMode] = useState(false)

  async function handleSubmit() {
    const trimmed = url.trim()
    if (!trimmed) return
    setLoading(true)
    setDemoMode(false)
    setTab('guide')
    setProfile(null)
    setSubmittedUrl('')
    try {
      const p = await api.postProfile(trimmed)
      setProfile(p)
      setSubmittedUrl(trimmed)
    } catch (error) {
      if (error instanceof ApiError) {
        void message.error(error.message)
      } else {
        setProfile(demoProfile)
        setSubmittedUrl(trimmed)
        setDemoMode(true)
        void message.info('后端暂未连接，已切换到本地演示模式')
      }
    } finally {
      setLoading(false)
    }
  }

  function startDemo() {
    setUrl(DEMO_URL)
    setProfile(demoProfile)
    setSubmittedUrl(DEMO_URL)
    setDemoMode(true)
    setTab('guide')
  }

  const showGuide = Boolean(profile && submittedUrl)

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">O</span><span>OpenGuide</span></div>
        <div className="topbar-note"><SafetyCertificateOutlined /> Evidence-first onboarding</div>
        <LlmSettings />
      </header>

      <main className="page-wrap">
        <section className="hero">
          <div className="hero-copy">
            <Tag className="eyebrow" icon={<CodeOutlined />}>OPEN SOURCE ONBOARDING</Tag>
            <Title>让第一个 PR<br /><span>不再是一座山</span></Title>
            <Paragraph>把陌生仓库变成一条可执行、可验证、有人陪你走完的贡献路线。</Paragraph>
            <div className="trust-row"><span><CheckCircleOutlined /> 真实仓库证据</span><span><CheckCircleOutlined /> 分步操作指引</span><span><CheckCircleOutlined /> 新手友好</span></div>
          </div>
          <div className="hero-orbit" aria-hidden="true">
            <div className="orbit orbit-one" /><div className="orbit orbit-two" />
            <div className="orbit-core"><GithubOutlined /></div>
            <span className="orbit-label label-one">README</span><span className="orbit-label label-two">ISSUES</span><span className="orbit-label label-three">TESTS</span>
          </div>
        </section>

        <section className="search-panel">
          <div className="panel-heading"><div><span className="section-kicker">START HERE</span><h2>输入一个 GitHub 仓库</h2></div><span className="step-count">01 / 03</span></div>
          <Space.Compact className="search-box">
            <Input size="large" placeholder="https://github.com/owner/repo" value={url} onChange={(e) => setUrl(e.target.value)} onPressEnter={handleSubmit} disabled={loading} prefix={<GithubOutlined />} />
            <Button type="primary" size="large" icon={<RocketOutlined />} loading={loading} onClick={handleSubmit}>生成路线图 <ArrowRightOutlined /></Button>
          </Space.Compact>
          <div className="search-foot"><span>不知道用哪个？</span><button onClick={startDemo}>体验 requests 示例 <ArrowRightOutlined /></button><span className="shortcut">Enter</span></div>
        </section>

        {!showGuide && !loading && <section className="feature-grid"><div><span className="feature-number">01</span><h3>先做仓库体检</h3><p>识别语言、构建方式、活跃度和 good-first-issue 信号。</p></div><div><span className="feature-number">02</span><h3>再生成贡献路线</h3><p>从环境搭建到首个 PR，每一步都写清楚预期结果。</p></div><div><span className="feature-number">03</span><h3>证据始终在场</h3><p>每条建议都能回到 README、issue 或真实代码来源。</p></div></section>}
      </main>

      {showGuide && (
        <div className="results-wrap">
        {demoMode && <div className="demo-banner"><ThunderboltOutlined /> 当前为本地演示数据（固定展示 psf/requests 示例路线图，与输入地址无关），启动后端后可分析任意公开仓库</div>}
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
              children: demoMode ? <GuideWizard guide={demoGuide} url={submittedUrl} /> : <GuideGenerator initialUrl={submittedUrl} />,
            },
            {
              key: 'health',
              label: (
                <Space>
                  <RocketOutlined /> 仓库体检
                </Space>
              ),
              children: profile ? <ProfileCard profile={profile} /> : null,
            },
            {
              key: 'ask',
              label: (
                <Space>
                  <QuestionCircleOutlined /> 贡献问答
                </Space>
              ),
              children: <GuidePage initialUrl={submittedUrl} />,
            },
          ]}
        />
        </div>
      )}
    </div>
  )
}
