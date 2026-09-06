import { useState } from 'react'
import { Button, Card, Divider, Input, List, Space, Tag, Typography, message } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

import { api, type SearchHit, type SearchResult } from '../api/client'

const { Title, Paragraph, Text } = Typography

const KIND_LABEL: Record<string, string> = {
  setup: '环境搭建',
  test: '测试基线',
  contribute: '贡献流程',
  arch: '架构/改文件',
  issue: '挑 issue',
  why: '原理',
}

const PERSPECTIVE_LABEL: Record<string, string> = {
  v1: '入口与约定',
  v2: '架构地图',
  v3: '可执行路径',
  v4: 'issue 槽位',
}

export default function GuidePage({ initialUrl }: { initialUrl: string }) {
  const [url, setUrl] = useState(initialUrl)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)

  async function handleSearch() {
    const u = url.trim()
    const q = query.trim()
    if (!u || !q) return
    setLoading(true)
    setResult(null)
    try {
      const r = await api.postSearch(u, q)
      setResult(r)
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '检索失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      <Title level={3} style={{ marginTop: 0 }}>
        仓库问答检索
      </Title>
      <Paragraph type="secondary">
        已解析仓库为视角索引；用自然语言问"怎么搭环境 / 跑测试 / 该改哪个文件"，返回带来源的证据片段。
      </Paragraph>

      <Card>
        <Space.Compact style={{ width: '100%' }}>
          <Input value={url} placeholder="仓库 URL" onChange={(e) => setUrl(e.target.value)} style={{ maxWidth: 320 }} />
          <Input
            value={query}
            placeholder="例如：how do I install and run tests / 挑一个 good-first-issue"
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={handleSearch}
          />
          <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={handleSearch}>
            检索
          </Button>
        </Space.Compact>
      </Card>

      {result && (
        <>
          <div style={{ marginTop: 14 }}>
            <Tag color="blue">识别意图: {KIND_LABEL[result.kind] ?? result.kind}</Tag>
            <Tag>命中视角: {result.perspective.split(',').map((p) => PERSPECTIVE_LABEL[p] ?? p).join(' / ')}</Tag>
          </div>

          <Divider>检索结果（{result.hits.length}）</Divider>
          <List
            dataSource={result.hits}
            renderItem={(h: SearchHit, i: number) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>#{i + 1}</Text>
                      <Tag>{PERSPECTIVE_LABEL[h.perspective] ?? h.perspective}</Tag>
                      <Text type="secondary">score {h.score}</Text>
                    </Space>
                  }
                  description={
                    <Text type="secondary" style={{ whiteSpace: 'pre-wrap' }}>
                      {h.text.length > 320 ? h.text.slice(0, 320) + '…' : h.text}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        </>
      )}
    </div>
  )
}
