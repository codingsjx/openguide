import { useEffect, useState } from 'react'
import { Form, Input, Modal, Space, Tag, message } from 'antd'
import { ApiOutlined } from '@ant-design/icons'

import { api } from '../../api/client'

const DEFAULTS = {
  base: 'https://api.openai.com/v1',
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
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="model" label="模型" initialValue={DEFAULTS.model}>
            <Input placeholder="gpt-5.5" />
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
