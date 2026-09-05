import { useState } from 'react'
import { Button, Card, Input, Space, Typography, message } from 'antd'
import { RocketOutlined } from '@ant-design/icons'

import { api } from '../api/client'
import type { Profile } from '../types/profile'
import ProfileCard from '../components/ProfileCard'

const { Title, Paragraph } = Typography

export default function HomePage() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit() {
    const trimmed = url.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    try {
      const p = await api.postProfile(trimmed)
      setProfile(p)
    } catch (e) {
      setProfile(null)
      setError(e instanceof Error ? e.message : '生成失败')
      void message.error(error ?? '生成失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Title level={2} style={{ marginBottom: 4 }}>
          OpenGuide
        </Title>
        <Paragraph type="secondary" style={{ fontSize: 16 }}>
          输入一个开源仓库 URL，AI 现场生成新手贡献路线图
        </Paragraph>
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
          />
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            loading={loading}
            onClick={handleSubmit}
          >
            体检仓库
          </Button>
        </Space.Compact>
      </Card>

      {profile && (
        <div style={{ marginTop: 20 }}>
          <ProfileCard profile={profile} />
        </div>
      )}

      {!profile && !loading && (
        <div style={{ textAlign: 'center', marginTop: 32 }}>
          <Typography.Text type="secondary">
            示例：https://github.com/psf/requests ｜ fastapi/fastapi ｜ vuejs/core
          </Typography.Text>
        </div>
      )}
    </div>
  )
}
