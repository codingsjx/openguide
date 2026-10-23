import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/types/savedGuide.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { parseSavedGuide } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const fixture = () => ({ repo_url: 'https://github.com/o/r', unsuitable: false, steps: [{ step_id: 1, stage: 'A', title: 'Install', command: null, evidence: { kind: 'missing', source: '', quote: '' } }] })

test('import marks saved content and provides safe display defaults', () => {
  const result = parseSavedGuide(JSON.stringify(fixture()))
  assert.equal(result.is_saved, true)
  assert.equal(result.steps[0].expected, '')
  assert.deepEqual(result.reasons, [])
})
test('external or script URLs are rejected', () => {
  assert.throws(() => parseSavedGuide(JSON.stringify({ ...fixture(), repo_url: 'javascript:alert(1)' })))
})
test('duplicate step IDs are rejected', () => {
  const f = fixture(); f.steps.push(f.steps[0])
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
test('non-text expected output cannot crash the React renderer', () => {
  const f = fixture(); f.steps[0].expected = { unexpected: true }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
test('invalid JSON fails without side effects', () => {
  assert.throws(() => parseSavedGuide('{bad json'))
})

test('stage generation modes are preserved and invalid modes rejected', () => {
  const f = fixture(); f.stage_modes = { A: 'llm', B: 'heuristic' }
  assert.deepEqual(parseSavedGuide(JSON.stringify(f)).stage_modes, f.stage_modes)
  f.stage_modes = { A: 'executed' }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
  f.stage_modes = { Z: 'llm' }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})

test('request provenance and safe fallback codes survive export/import', () => {
  const f = fixture(); f.requested_mode = 'ai'; f.stage_fallbacks = { A: 'model_timeout' }
  assert.equal(parseSavedGuide(JSON.stringify(f)).stage_fallbacks.A, 'model_timeout')
  f.requested_mode = 'guessed'
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
  f.requested_mode = 'ai'; f.stage_fallbacks = { A: 'raw provider error' }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
test('invalid command derivation cannot crash rendering', () => {
  const f = fixture(); f.steps[0].command_derivation = { unexpected: true }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
test('execution result cannot be attached to another command or commit', () => {
  const f = fixture()
  f.default_branch = 'a'.repeat(40)
  f.steps[0].command = 'pytest tests'
  f.steps[0].execution_record = { status: 'passed', command: 'pytest unrelated', commit_sha: f.default_branch, environment: 'test', summary: 'ok', report: 'report.json' }
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
  f.steps[0].execution_record.command = f.steps[0].command
  assert.equal(parseSavedGuide(JSON.stringify(f)).steps[0].execution_record.status, 'passed')
})
test('working directory cannot escape the checkout', () => {
  const f = fixture(); f.steps[0].working_directory = '../outside'
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})

test('document-derived directories survive saved guide import', () => {
  const f = fixture(); f.steps[0].working_directory = 'frontend'; f.steps[0].directory_basis = 'document_context'
  f.stage_fallbacks = { A: 'incomplete_workflow' }
  assert.equal(parseSavedGuide(JSON.stringify(f)).stage_fallbacks.A, 'incomplete_workflow')
  assert.equal(parseSavedGuide(JSON.stringify(f)).steps[0].directory_basis, 'document_context')
  f.steps[0].directory_basis = 'model_guess'
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
test('prerequisites cannot point forward or to nonexistent steps', () => {
  const f = fixture(); f.steps[0].prerequisite_step_ids = [2]
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})

test('saved issue entries retain their snapshot but reject hostile links and shapes', () => {
  const f = fixture()
  f.issue_discovery = { status: 'untriaged', reason: 'browse only', sampled_at: '', sampled_count: 1, blocked_count: 0,
    candidates: [{ number: 3, title: 'Task', url: 'https://github.com/o/r/issues/3', labels: [], checks: ['check latest state'], origin: 'untriaged' }],
    search_links: [{ label: 'Open issues', url: 'https://github.com/o/r/issues?q=is%3Aopen' }] }
  assert.equal(parseSavedGuide(JSON.stringify(f)).issue_discovery.candidates[0].number, 3)
  f.issue_discovery.candidates[0].url = 'javascript:alert(1)'
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
  f.issue_discovery.candidates[0].url = 'https://github.com/o/r/issues/3'
  f.issue_discovery.search_links[0].url = 'https://evil.test/issues'
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
  f.issue_discovery.search_links[0].url = 'https://github.com/o/r/issues'
  f.issue_discovery.candidates[0].checks = {}
  assert.throws(() => parseSavedGuide(JSON.stringify(f)))
})
