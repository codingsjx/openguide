import { useState } from 'react'
import { Button, Card, Input, Space, Tag, Typography, message } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../../api/client'
import type { Guide } from '../../types/guide'
import GuideWizard from '../GuideWizard'

const { Title, Paragraph } = Typography

export default function GuideGenerator({ initialUrl }: { initialUrl: string }) {
  const [url, setUrl] = useState(initialUrl)
  const [loading, setLoading] = useState(false)
  const [guide, setGuide] = useState<Guide | null>(null)

  async function generate(useLlm: boolean) {
    const u = url.trim()
    if (!u) return
    setLoading(true)
    setGuide(null)
    try {
      const g = await api.postGuide(u, useLlm)
      setGuide(g)
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '生成失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 940, margin: '0 auto' }}>
      <Title level={4} style={{ marginTop: 0 }}>
        生成贡献指南
      </Title>
      <Paragraph type="secondary">
        输入仓库后生成**结构化、带证据**的分步新手贡献指南（Stage A 环境搭建 → B 测试 → C 挑 issue → D 首 PR）。
      </Paragraph>

      <Card size="small">
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={url}
            placeholder="仓库 URL"
            onChange={(e) => setUrl(e.target.value)}
          />
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={loading}
            onClick={() => generate(true)}
          >
            用 AI 生成
          </Button>
          <Button loading={loading} onClick={() => generate(false)}>
            快速(本地规则)
          </Button>
        </Space.Compact>
      </Card>

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
