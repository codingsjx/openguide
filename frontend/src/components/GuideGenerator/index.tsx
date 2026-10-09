import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Input, Space, Tag, Typography } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../../api/client'
import type { Guide } from '../../types/guide'
import GuideWizard from '../GuideWizard'

const { Title, Paragraph, Text } = Typography

export default function GuideGenerator({ initialUrl }: { initialUrl: string }) {
  const [url, setUrl] = useState(initialUrl)
  const [loading, setLoading] = useState(false)
  const [guide, setGuide] = useState<Guide | null>(null)
  const [error, setError] = useState<string | null>(null)
  const lastUrlRef = useRef('')

  const generate = useCallback(async (targetUrl: string, useLlm: boolean) => {
    const u = targetUrl.trim()
    if (!u) return
    setLoading(true)
    setGuide(null)
    setError(null)
    try {
      const g = await api.postGuide(u, useLlm)
      setGuide(g)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // 顶部搜索框提交了新的仓库地址时：同步输入框内容、清掉旧路线图，
  // 并自动为这个新地址重新生成，避免"换了地址路线图却不变"。
  useEffect(() => {
    const nextUrl = initialUrl.trim()
    if (!nextUrl || nextUrl === lastUrlRef.current) return
    lastUrlRef.current = nextUrl
    setUrl(nextUrl)
    void generate(nextUrl, true)
  }, [generate, initialUrl])

  return (
    <div style={{ maxWidth: 940, margin: '0 auto' }}>
      <Title level={4} style={{ marginTop: 0 }}>
        生成贡献指南
      </Title>
      <Paragraph type="secondary">
        输入仓库后生成<Text strong>结构化、带证据</Text>的分步新手贡献指南（Stage A 环境搭建 → B 测试 → C 挑 issue → D 首 PR）。
      </Paragraph>

      <Card size="small">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Input
            value={url}
            placeholder="仓库 URL"
            onChange={(e) => setUrl(e.target.value)}
            onPressEnter={() => generate(url, true)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <Space.Compact>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={loading}
              onClick={() => generate(url, true)}
            >
              用 AI 生成
            </Button>
            <Button loading={loading} onClick={() => generate(url, false)}>
              快速(本地规则)
            </Button>
          </Space.Compact>
        </div>
      </Card>

      {loading && (
        <Alert
          showIcon
          type="info"
          message="正在生成贡献路线图"
          description="正在读取仓库文档、issue 和构建配置，通常需要 10–60 秒，请稍候。"
          style={{ marginTop: 12 }}
        />
      )}

      {error && (
        <Alert
          showIcon
          type="error"
          message="路线图生成失败"
          description={error}
          style={{ marginTop: 12 }}
          action={
            <Button size="small" onClick={() => generate(url, false)}>
              改用本地规则
            </Button>
          }
        />
      )}

      {guide && (
        <div style={{ marginTop: 8 }}>
          <Space style={{ marginBottom: 4 }}>
            {guide.unsuitable && <Tag color="red">暂不建议贡献</Tag>}
            <Tag>{guide.steps.length} 步</Tag>
          </Space>
          <GuideWizard guide={guide} url={guide.repo_url} />
        </div>
      )}
    </div>
  )
}
