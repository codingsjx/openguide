import { useState } from 'react'
import { Alert, Button, Tabs, Input, Space, Typography, message, Tag, Upload } from 'antd'
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

import { api } from '../api/client'
import type { Profile } from '../types/profile'
import ProfileCard from '../components/ProfileCard'
import GuideGenerator from '../components/GuideGenerator'
import LlmSettings from '../components/LlmSettings'
import GuidePage from './GuidePage'
import GuideWizard from '../components/GuideWizard'
import type { Guide } from '../types/guide'
import { parseSavedGuide } from '../types/savedGuide'

const { Title, Paragraph } = Typography

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

  async function handleSubmit() {
    const trimmed = url.trim()
    if (!trimmed) return
    if (loading) return
    setProfileError(null)
    setLoading(true)
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
            <Paragraph>从仓库资料中查找上手步骤，核对原文，再走向第一次贡献。</Paragraph>
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
          {profileError && <Alert showIcon type="error" message="仓库读取失败" description={profileError} style={{ marginTop: 12 }} />}
          <div className="search-foot"><span>不知道用哪个？</span><button onClick={startDemo}>体验 requests 示例 <ArrowRightOutlined /></button><span className="shortcut">Enter</span></div>
          <Upload accept=".json" showUploadList={false} beforeUpload={async (file) => {
            try {
              if (file.size > 2_000_000) throw new Error('指南文件不能超过 2 MB')
              const imported = parseSavedGuide(await file.text())
              setSavedGuide(imported)
              setGuideVersion((version) => version + 1)
              setSubmittedUrl(imported.repo_url)
              setDemoMode(false)
              setTab('guide')
            } catch (error) { void message.error(error instanceof Error ? error.message : '导入失败') }
            return false
          }}><Button type="link" style={{ paddingLeft: 0 }}>导入已保存指南（本机离线查看）</Button></Upload>
        </section>

        {!showGuide && !loading && <section className="feature-grid"><div><span className="feature-number">01</span><h3>先做仓库体检</h3><p>识别语言、构建方式、活跃度和 good-first-issue 信号。</p></div><div><span className="feature-number">02</span><h3>再生成贡献路线</h3><p>分阶段查看操作建议，缺少资料时明确提示。</p></div><div><span className="feature-number">03</span><h3>核对原文依据</h3><p>区分来源存在、原文匹配与尚未验证的内容。</p></div></section>}
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
              children: savedGuide ? <GuideWizard key={`saved-${guideVersion}`} guide={savedGuide} url={savedGuide.repo_url} /> : demoMode ? <GuideWizard key={`demo-${guideVersion}`} guide={demoGuide} url={submittedUrl} /> : <GuideGenerator initialUrl={submittedUrl} />,
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
              children: <GuidePage initialUrl={submittedUrl} />,
            },
          ]}
        />
        </div>
      )}
    </div>
  )
}
