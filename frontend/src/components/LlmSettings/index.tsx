import { useEffect, useState } from 'react'
import { Button, Form, Input, Modal, Space, message } from 'antd'
import { ApiOutlined } from '@ant-design/icons'

import { api } from '../../api/client'

export default function LlmSettings() {
  const [open, setOpen] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    let active = true
    api
      .getLlmConfig()
      .then((r) => {
        if (active) setConfigured(r.configured)
      })
      .catch(() => {
        if (active) setConfigured(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function handleOk() {
    const v = await form.validateFields()
    try {
      const r = await api.setLlmConfig({
        api_key: v.api_key ?? '',
        base_url: v.base_url?.trim() || '',
        model: v.model?.trim() || '',
      })
      setConfigured(r.configured)
      form.resetFields(['api_key'])
      setOpen(false)
      void message.success('LLM 设置已保存（仅当前会话有效）')
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '保存失败')
    }
  }

  return (
    <div style={{ display: 'inline-block' }}>
      <Button
        className="llm-trigger"
        onClick={() => setOpen(true)}
        icon={<ApiOutlined />}
      >
        <span className={`llm-status-dot${configured ? '' : ' unconfigured'}`} />{configured ? '模型配置（已填写）' : '配置模型'}
      </Button>
      <Modal
        title="设置 LLM（你自己的中转/官方 API）"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleOk}
        okText="保存"
        cancelText="取消"
      >
        <p style={{ color: '#888' }}>
          Key 会发送到当前后端，只在本页面会话对应的服务器内存中保留，不写入文件。刷新页面、后端重启或闲置 30 分钟后需重新填写；其他页面不会继承此配置。公网部署还需访问控制与用量限制。
        </p>
        <p>留空的设置沿用本页或后端配置，不会自动替换接口。已填写配置不代表模型服务当前可用。</p>
        <Form form={form} layout="vertical">
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: !configured, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="留空沿用现有接口" />
          </Form.Item>
          <Form.Item name="model" label="模型">
            <Input placeholder="留空沿用现有模型" />
          </Form.Item>
        </Form>
        <Space direction="vertical" size={4}>
          <span style={{ color: '#888' }}>任何 OpenAI 兼容端点均可：官方直连（https://api.openai.com/v1），或你自选的第三方中转。</span>
          <span style={{ color: '#888' }}>使用第三方中转时，请遵循其服务条款；相关说明见 docs/third_party_disclosure.md。</span>
        </Space>
      </Modal>
    </div>
  )
}
