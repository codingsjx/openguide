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
