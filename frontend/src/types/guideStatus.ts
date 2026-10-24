import type { Guide } from './guide'

export const fallbackLabels: Record<string, string> = {
  not_configured: '生成时未配置模型', model_timeout: '模型请求超时',
  model_auth_failed: '模型服务拒绝认证或权限', model_rate_limited: '模型服务限流',
  model_error: '模型请求未完成', invalid_output: '模型输出格式或步骤无效',
  evidence_unverified: 'AI 步骤未保留可核验出处',
  incomplete_workflow: 'AI 步骤缺少原文操作入口，已补齐',
  no_stage_evidence: '本阶段无可引用资料，未调用模型',
}

export function guideStatus(guide: Guide): { title: string; description: string; type: 'info' | 'warning' } {
  const suffix = '命令仍需在本机验证。'
  let result: { title: string; description: string; type: 'info' | 'warning' }
  const reasons = Object.values(guide.stage_fallbacks ?? {})
  if (guide.is_demo) return { title: '静态交互示例', description: '尚未分析当前仓库；正式生成后再核对原文和操作。', type: 'info' }
  if (guide.requested_mode === 'rules') {
    result = { title: '规则模式 · 由你选择', description: '你选择了“快速（本地规则）”，这次生成没有调用模型。' + suffix, type: 'info' }
  } else if (guide.requested_mode === 'ai' && reasons.includes('not_configured')) {
    result = { title: '生成时未配置模型，已使用规则整理', description: '你请求了 AI 生成，但生成时没有可用的模型配置。请检查模型设置后重试。' + suffix, type: 'warning' }
  } else if (guide.requested_mode === 'ai' && reasons.some((r) => !['evidence_unverified', 'incomplete_workflow', 'no_stage_evidence'].includes(r))) {
    result = { title: guide.generation_mode === 'heuristic' ? 'AI 生成未完成，已使用规则整理' : '部分 AI 阶段未完成，已保留其余结果',
      description: '查看下方各阶段的来源和回退原因；可检查模型服务后用 AI 重新生成。' + suffix, type: 'warning' }
  } else if (guide.requested_mode === 'ai' && reasons.includes('no_stage_evidence')) {
    result = { title:'按现有资料整理，部分阶段未调用模型', description:'没有可引用资料的阶段保留规则入口与待确认项；各阶段的生成方式可展开查看。' + suffix, type:'info' }
  } else if (guide.generation_mode === 'llm') {
    result = { title: 'AI 指南已生成', description: suffix, type: 'info' }
  } else if (guide.generation_mode === 'mixed') {
    result = { title: 'AI 与规则共同整理', description: '部分步骤使用规则入口或原文命令展开；具体来源见各阶段。' + suffix, type: 'info' }
  } else {
    result = { title: '规则整理 · 触发原因未记录', description: '这份指南没有记录生成时选择的模式，无法判断是否发生过 AI 回退；重新生成后可查看原因。' + suffix, type: 'info' }
  }
  if (guide.is_saved) return { ...result, title: '已保存 · ' + result.title, description: '本次仅在本机查看，没有重新采集资料或执行命令。' + result.description }
  return result
}

export function groupGuideWarnings(warnings: string[] = []) {
  const groups = { collection: [] as string[], preparation: [] as string[], generation: [] as string[], reference: [] as string[], other: [] as string[] }
  for (const text of new Set(warnings)) {
    if (/文件证据固定于提交|已保存指南仅在本机|静态交互示例/.test(text)) groups.reference.push(text)
    else if (/阶段未保留|阶段模型未完成|阶段未覆盖|阶段缺少|阶段没有取得可引用资料|模型不可用|模型连接提前关闭|部分 make 命令/.test(text)) groups.generation.push(text)
    else if (/符号链接|Windows 克隆/.test(text)) groups.preparation.push(text)
    else if (/抓取失败|采样失败|未取得|未完整取得|未完整成功|信息未取得|超过大小限制|截断|覆盖不完整/.test(text)) groups.collection.push(text)
    else groups.other.push(text)
  }
  return groups
}
