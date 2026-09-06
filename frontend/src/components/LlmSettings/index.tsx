import { useEffect, useState } from 'react'
import { Form, Input, Modal, Space, Tag, message } from 'antd'
import { ApiOutlined } from '@ant-design/icons'

import { api } from '../../api/client'

const DEFAULTS = {
  base: 'https://api.a6api.com/v1',
  model: 'gpt-5.5',
}

export default function LlmSettings() {
  const [open, setOpen] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [form] = Form.useForm()

  async function refresh() {
    try {
      const r = await api.getLlmConfig()
      setConfigured(r.configured)
    } catch {
      setConfigured(false)
    }
  }
  useEffect(() => {
    void refresh()
  }, [])

  async function handleOk() {
    const v = await form.validateFields()
    try {
      const r = await api.setLlmConfig({
        api_key: v.api_key ?? '',
        base_url: v.base_url || DEFAULTS.base,
        model: v.model || DEFAULTS.model,
      })
      setConfigured(r.configured)
      setOpen(false)
      void message.success('LLM 设置已保存（仅当前会话有效）')
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '保存失败')
    }
  }

  return (
    <div style={{ display: 'inline-block' }}>
      <Tag
        onClick={() => setOpen(true)}
        color={configured ? 'green' : 'orange'}
        style={{ cursor: 'pointer' }}
      >
        <ApiOutlined /> {configured ? 'LLM 已配置' : '设置我的 LLM'}
      </Tag>
      <Modal
        title="设置 LLM（你自己的中转/官方 API）"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={handleOk}
        okText="保存"
        cancelText="取消"
      >
        <p style={{ color: '#888' }}>
          Key 仅保存在本会话内存中，不写入磁盘，也不会上传；重启后需重新填写。
        </p>
        <Form form={form} layout="vertical">
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" initialValue={DEFAULTS.base}>
            <Input placeholder="https://api.a6api.com/v1" />
          </Form.Item>
          <Form.Item name="model" label="模型" initialValue={DEFAULTS.model}>
            <Input placeholder="gpt-5.5" />
          </Form.Item>
        </Form>
        <Space direction="vertical" size={4}>
          <span style={{ color: '#888' }}>默认中转：https://api.a6api.com/v1（模型含 gpt-5.5 / claude-opus-5 / deepseek 等）</span>
          <span style={{ color: '#888' }}>官方直连亦可（如 https://api.deepseek.com/v1 + deepseek-chat）。</span>
        </Space>
      </Modal>
    </div>
  )
}
