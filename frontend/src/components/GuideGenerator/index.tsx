import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Input, InputNumber, Modal, Space, Tag, Typography } from 'antd'
import { ClockCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../../api/client'
import type { Guide } from '../../types/guide'
import { downloadGuide } from '../../types/savedGuide'
import { DEFAULT_GUIDE_TIMEOUT, MIN_GUIDE_TIMEOUT, MAX_GUIDE_TIMEOUT, isGuideTimeout, guideRequestTimeoutMs, loadGuideTimeout, saveGuideTimeout } from '../../types/guideTimeout'
import GuideWizard from '../GuideWizard'

const { Title, Paragraph, Text } = Typography

export default function GuideGenerator({ initialUrl, initialUseLlm = true }: { initialUrl: string; initialUseLlm?: boolean }) {
  const [url, setUrl] = useState(initialUrl)
  const [loading, setLoading] = useState(false)
  const [guide, setGuide] = useState<Guide | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cancelled, setCancelled] = useState(false)
  const lastUrlRef = useRef('')
  const activeRequest = useRef<AbortController | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [modelTimeout, setModelTimeout] = useState(loadGuideTimeout)
  const timeoutRef = useRef(modelTimeout)
  const [timeoutOpen, setTimeoutOpen] = useState(false)
  const [timeoutDraft, setTimeoutDraft] = useState<number | null>(modelTimeout)
  const [requestSettings, setRequestSettings] = useState<{ ai: boolean; seconds: number } | null>(null)

  function applyTimeout() {
    if (!isGuideTimeout(timeoutDraft)) return
    timeoutRef.current = timeoutDraft
    setModelTimeout(timeoutDraft)
    saveGuideTimeout(timeoutDraft)
    setTimeoutOpen(false)
  }

  useEffect(() => {
    if (!loading) return
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [loading])
  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
    // React StrictMode replays effects on mount; allow that setup to restart
    // the request instead of leaving the first, aborted request as "loaded".
    lastUrlRef.current = ''
  }, [])

  const generate = useCallback(async (targetUrl: string, useLlm: boolean) => {
    const u = targetUrl.trim()
    if (!u) return
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setElapsed(0)
    setLoading(true)
    // Keep the current guide and its contribution work visible until the new
    // result succeeds. Session memory also survives a changed workflow key.
    setError(null)
    setCancelled(false)
    const seconds = timeoutRef.current
    setRequestSettings({ ai: useLlm, seconds })
    try {
      const g = await api.postGuide(u, useLlm, controller.signal, seconds)
      if (activeRequest.current === controller) setGuide(g)
    } catch (e) {
      if (activeRequest.current === controller) {
        if (controller.signal.aborted) setCancelled(true)
        else setError(e instanceof Error ? e.message : '生成失败')
      }
    } finally {
      if (activeRequest.current === controller) setLoading(false)
    }
  }, [])

  // 顶部搜索框提交了新的仓库地址时：同步输入框内容、清掉旧路线图，
  // 并自动为这个新地址重新生成，避免"换了地址路线图却不变"。
  useEffect(() => {
    const nextUrl = initialUrl.trim()
    if (!nextUrl || nextUrl === lastUrlRef.current) return
    setUrl(nextUrl)
    // StrictMode replays mount effects. Cancel the scheduled first setup
    // before it sends a second, billable automatic model request.
    const timer = window.setTimeout(() => {
      lastUrlRef.current = nextUrl
      void generate(nextUrl, initialUseLlm)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [generate, initialUrl, initialUseLlm])

  return (
    <div className="guide-generator">
      <div className="section-heading"><span className="section-kicker">CONTRIBUTION GUIDE</span>
      <Title level={4} style={{ marginTop: 0 }}>
        生成贡献指南
      </Title>
      <Paragraph type="secondary">
        输入仓库后生成<Text strong>结构化、带证据</Text>的分步新手贡献指南（Stage A 环境搭建 → B 测试 → C 挑 issue → D 首 PR）。
      </Paragraph>
      </div>

      <Card size="small" className="generation-controls">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Input
            value={url}
            disabled={loading}
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
          <Button icon={<ClockCircleOutlined />} onClick={() => { setTimeoutDraft(modelTimeout); setTimeoutOpen(true) }}>
            超时设置 · {modelTimeout} 秒
          </Button>
        </div>
      </Card>

      <Modal title="AI 请求超时设置" open={timeoutOpen} onCancel={() => setTimeoutOpen(false)} onOk={applyTimeout}
        okText="保存设置" cancelText="取消" okButtonProps={{ disabled: !isGuideTimeout(timeoutDraft) }}>
        <Paragraph>设置贡献指南每批讲解的模型网络等待时间，支持 {MIN_GUIDE_TIMEOUT}–{MAX_GUIDE_TIMEOUT} 秒。</Paragraph>
        <Space wrap style={{ marginBottom: 16 }}>
          {[25, 45, 60, 90, 120].map((seconds) => <Button key={seconds} type={timeoutDraft === seconds ? 'primary' : 'default'} onClick={() => setTimeoutDraft(seconds)}>{seconds} 秒</Button>)}
        </Space>
        <div><label htmlFor="guide-model-timeout">自定义秒数：</label><InputNumber id="guide-model-timeout" aria-label="模型请求超时秒数"
          min={MIN_GUIDE_TIMEOUT} max={MAX_GUIDE_TIMEOUT} precision={0} value={timeoutDraft} onChange={setTimeoutDraft} /></div>
        {isGuideTimeout(timeoutDraft) && <Paragraph style={{ marginTop: 12 }}>AI 讲解按小批次处理，模型等待总预算最多为所选值的四倍；页面整次等待上限约 {Math.ceil(guideRequestTimeoutMs(timeoutDraft) / 1000)} 秒，包含资料采集预留时间。网络等待设置不等于整个流程的硬截止。</Paragraph>}
        <Paragraph type="secondary">保存后用于下一次 AI 生成，正在进行的请求保持原设置。延长等待时间不保证模型成功返回；仍可取消等待。设置保存在当前浏览器。</Paragraph>
        <Button type="link" onClick={() => setTimeoutDraft(DEFAULT_GUIDE_TIMEOUT)}>恢复默认 25 秒</Button>
      </Modal>

      {loading && (
        <Alert
          showIcon
          type="info"
          message="正在生成贡献路线图"
          description={`已等待 ${elapsed} 秒。${requestSettings?.ai ? `本次每批模型等待设置为 ${requestSettings.seconds} 秒，页面整次等待上限约 ${guideRequestTimeoutMs(requestSettings.seconds) / 1000} 秒。` : ''}正在处理仓库资料与指南。取消仅停止本页等待，后台处理可能继续。`}
          action={<Button size="small" onClick={() => activeRequest.current?.abort()}>取消等待</Button>}
          style={{ marginTop: 12 }}
        />
      )}

      {cancelled && <Alert showIcon type="info" message="已取消等待" description="后台可能仍在完成当前处理。你可以重新生成，或选择本地规则；本地规则也需要仓库资料。" style={{ marginTop: 12 }} />}

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
          {loading && <Alert showIcon type="info" style={{ marginBottom: 12 }} message="正在更新，下方保留上一份指南与本页准备记录"
            description={`当前显示 ${guide.owner}/${guide.repo} · ${guide.default_branch.slice(0, 12)}；新结果返回前不会用它代替新仓库资料。`} />}
          <div className="guide-metadata">
            {guide.unsuitable && <Tag color="red">暂不建议贡献</Tag>}
            <Tag>{guide.steps.length} 步</Tag>
            {guide.model_timeout_s != null && <Tag>本次模型等待：{guide.model_timeout_s} 秒/{guide.generation_strategy === 'source_then_explain' ? '批次' : '阶段'}</Tag>}
            <Button size="small" onClick={() => downloadGuide(guide)}>保存指南 JSON</Button>
          </div>
          <GuideWizard guide={guide} url={guide.repo_url}
            onRegenerateAi={loading ? undefined : () => generate(guide.repo_url, true)}
            onRegenerate={loading ? undefined : () => generate(guide.repo_url, guide.requested_mode !== 'rules')} />
        </div>
      )}
    </div>
  )
}
