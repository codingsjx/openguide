import { Card, Col, Progress, Row, Statistic, Tag, Tooltip, Typography } from 'antd'
import {
  BranchesOutlined,
  CheckCircleOutlined,
  CommentOutlined,
  FileTextOutlined,
  GithubOutlined,
  StarOutlined,
} from '@ant-design/icons'

import type { Profile } from '../../types/profile'

const { Text, Title, Paragraph } = Typography

const SUIT_COLOR: Record<string, string> = {
  promising: 'green',
  unclear: 'orange',
  avoid: 'red',
}

export default function ProfileCard({ profile }: { profile: Profile }) {
  const langs = Object.entries(profile.languages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, frac]) => ({ name, pct: Math.round(frac * 100) }))
  const build = profile.build
  const hasBuildInfo = Boolean(build?.tool || build?.test_cmd)

  return (
    <Card style={{ maxWidth: 860, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
        }}
      >
        <div>
          <Title level={4} style={{ marginTop: 0, marginBottom: 4 }}>
            <GithubOutlined /> {profile.owner}/{profile.repo}
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 8 }}>
            {profile.description || '（无描述）'}
          </Paragraph>
          <div>
            <Tag color="blue">{profile.license ? `License: ${profile.license}` : '无许可证'}</Tag>
            <Tag>默认分支 {profile.default_branch}</Tag>
            {profile.has_readme && <Tag color="cyan">README</Tag>}
            {profile.has_contributing && <Tag color="cyan">CONTRIBUTING</Tag>}
            {profile.has_docs && <Tag color="cyan">docs/</Tag>}
          </div>
        </div>
        <Tag
          color={SUIT_COLOR[profile.suitability]}
          style={{ fontSize: 15, padding: '2px 10px' }}
        >
          {profile.suitability === 'promising'
            ? '适合新手'
            : profile.suitability === 'unclear'
              ? '信号偏弱'
              : '暂不建议'}
        </Tag>
      </div>

      <Row gutter={[12, 12]} style={{ marginTop: 8 }}>
        <Col span={6}>
          <Statistic title="Star" value={profile.stars} prefix={<StarOutlined />} />
        </Col>
        <Col span={6}>
          <Statistic title="Fork" value={profile.forks} prefix={<BranchesOutlined />} />
        </Col>
        <Col span={6}>
          <Statistic
            title="open issues"
            value={profile.open_issues}
            prefix={<CommentOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic title="30 天提交" value={profile.activity.commits_30d} />
        </Col>
      </Row>

      {langs.length > 0 && (
        <>
          <Text strong style={{ display: 'block', margin: '12px 0 4px' }}>
            语言构成
          </Text>
          <Row>
            {langs.map((l) => (
              <Col span={8} key={l.name}>
                <Tooltip title={`${l.name}: ${l.pct}%`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text style={{ width: 90, whiteSpace: 'nowrap' }} ellipsis>
                      {l.name}
                    </Text>
                    <Progress
                      percent={l.pct}
                      size={{ height: 8, width: undefined }}
                      style={{ flex: 1 }}
                    />
                  </div>
                </Tooltip>
              </Col>
            ))}
          </Row>
        </>
      )}

      <div style={{ marginTop: 14 }}>
        <Text strong>构建与测试</Text>
        <div
          style={{
            display: 'flex',
            gap: 8,
            marginTop: 6,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <Tag icon={<FileTextOutlined />}>
            {hasBuildInfo ? `构建: ${build!.tool}` : '未识别到构建文件'}
          </Tag>
          {build?.test_cmd && <Tag color="purple">测试: {build.test_cmd}</Tag>}
        </div>
      </div>

      <div style={{ marginTop: 14 }}>
        <Text strong>AI 体检建议</Text>
        <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
          {profile.reasons.map((r, i) => (
            <li key={i}>
              <Text type="secondary">{r}</Text>
            </li>
          ))}
        </ul>
      </div>

      {profile.gfi.count > 0 && (
        <div style={{ marginTop: 12 }}>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />{' '}
          <Text>有 {profile.gfi.count} 个 good-first-issue 可挑选，适合首次贡献切入</Text>
        </div>
      )}
    </Card>
  )
}
