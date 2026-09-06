import { useState } from 'react'
import { Button, Card, Tabs, Input, Space, Typography, message } from 'antd'
import { GithubOutlined, QuestionCircleOutlined, RocketOutlined, ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../api/client'
import type { Profile } from '../types/profile'
import ProfileCard from '../components/ProfileCard'
import GuideGenerator from '../components/GuideGenerator'
import LlmSettings from '../components/LlmSettings'
import GuidePage from './GuidePage'

const { Title, Paragraph } = Typography

export default function HomePage() {
  const [url, setUrl] = useState('')
  const [tab, setTab] = useState<string>('health')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [submittedUrl, setSubmittedUrl] = useState('')

  async function handleSubmit() {
    const trimmed = url.trim()
    if (!trimmed) return
    setLoading(true)
    try {
      const p = await api.postProfile(trimmed)
      setProfile(p)
      setSubmittedUrl(trimmed)
    } catch (e) {
      setProfile(null)
      void message.error(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const showGuide = Boolean(profile && submittedUrl)

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <Title level={2} style={{ marginBottom: 4 }}>
          OpenGuide
        </Title>
        <Paragraph type="secondary" style={{ fontSize: 15 }}>
          输入一个开源仓库 URL，AI 现场生成新手贡献路线图
        </Paragraph>
      </div>

      <div style={{ textAlign: 'right', marginBottom: 8 }}>
        <LlmSettings />
      </div>

      <Card>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            size="large"
            placeholder="https://github.com/owner/repo 或 owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onPressEnter={handleSubmit}
            disabled={loading}
            prefix={<GithubOutlined />}
          />
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            loading={loading}
            onClick={handleSubmit}
          >
            生成新手路线图
          </Button>
        </Space.Compact>
      </Card>

      {showGuide && (
        <Tabs
          activeKey={tab}
          onChange={setTab}
          style={{ marginTop: 16 }}
          items={[
            {
              key: 'guide',
              label: (
                <Space>
                  <ThunderboltOutlined /> 贡献指南
                </Space>
              ),
              children: <GuideGenerator initialUrl={submittedUrl} />,
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
      )}

      {!showGuide && !loading && (
        <div style={{ textAlign: 'center', marginTop: 28 }}>
          <Typography.Text type="secondary">
            示例：https://github.com/psf/requests ｜ fastapi/fastapi ｜ vuejs/core
          </Typography.Text>
        </div>
      )}
    </div>
  )
}
