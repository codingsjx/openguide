import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/types/guideStatus.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { guideStatus, groupGuideWarnings } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('full AI tutoring coverage is distinct from source operations and partial failure', () => {
  const g = { requested_mode: 'ai', generation_strategy: 'source_then_explain', steps: [{ ai_explanation: 'ready' }, { ai_explanation: 'ready' }] }
  assert.equal(guideStatus(g).type, 'info')
  assert.match(guideStatus(g).description, /2\/2/)
  g.steps[1].ai_explanation = ''
  assert.equal(guideStatus(g).type, 'warning')
  assert.match(guideStatus(g).description, /1\/2/)
})

test('explicit rule choice is distinguished from missing model configuration', () => {
  const manual = guideStatus({ requested_mode: 'rules', generation_mode: 'heuristic' })
  assert.match(manual.title, /由你选择/)
  assert.equal(manual.type, 'info')
  const missing = guideStatus({ requested_mode: 'ai', generation_mode: 'heuristic', stage_fallbacks: { A: 'not_configured' } })
  assert.match(missing.title, /未配置模型/)
  assert.equal(missing.type, 'warning')
})
test('model request failures are visible, evidence fallback is explained without calling it an outage', () => {
  assert.equal(guideStatus({ requested_mode: 'ai', generation_mode: 'mixed', stage_fallbacks: { B: 'model_timeout' } }).type, 'warning')
  assert.equal(guideStatus({ requested_mode: 'ai', generation_mode: 'mixed', stage_fallbacks: { C: 'evidence_unverified' } }).type, 'info')
})

test('skipped empty stages are explicit without blaming the model service', () => {
  const status=guideStatus({requested_mode:'ai',generation_mode:'mixed',stage_fallbacks:{C:'no_stage_evidence'}})
  assert.equal(status.type,'info')
  assert.match(status.title,/未调用模型/)
  assert.doesNotMatch(status.description,/检查模型服务/)
  assert.equal(groupGuideWarnings(['挑选 issue阶段没有取得可引用资料，未调用模型；已保留规则入口与待确认项。']).generation.length,1)
})
test('legacy saved guides never invent a historical button choice', () => {
  const status = guideStatus({ generation_mode: 'heuristic', is_saved: true })
  assert.match(status.title, /触发原因未记录/)
  assert.match(status.description, /没有重新采集/)
  assert.doesNotMatch(status.title, /由你选择/)
})
test('screenshot warnings are split without dropping a collection failure', () => {
  const warnings = ['语言信息抓取失败，不能按空结果判断', '文件证据固定于提交 abc；issue 信息是独立采集的快照。',
    '仓库含 2 个符号链接；Windows 克隆后请确认链接', '挑选 issue阶段未保留可核验依据，已补充规则入口。']
  const groups = groupGuideWarnings(warnings)
  assert.equal(groups.collection.length, 1)
  assert.equal(groups.reference.length, 1)
  assert.equal(groups.preparation.length, 1)
  assert.equal(groups.generation.length, 1)
  assert.deepEqual(Object.values(groups).flat().sort(), warnings.sort())
})
test('partial docs and missing activity remain collection notices; unknown text is preserved', () => {
  const groups = groupGuideWarnings(['部分文档抓取失败，仅能依据已取得的原文生成', '提交活跃度未取得，不能按零提交判断', '新增未知说明'])
  assert.equal(groups.collection.length, 2)
  assert.deepEqual(groups.other, ['新增未知说明'])
})
