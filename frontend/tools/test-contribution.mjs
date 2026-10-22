import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/types/contribution.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { emptyContribution, contributionProblems, buildContributionDraft, changedFiles } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const guide = { repo_url: 'https://github.com/o/r', default_branch: 'a'.repeat(40), steps: [] }
const input = () => ({ ...emptyContribution(), task: 'Document prerequisites', issueUrl: guide.repo_url + '/issues/3', problem: 'Instructions omit a prerequisite', changeSummary: 'Added the prerequisite', files: 'CONTRIBUTING.md' })

test('a task without actual change records cannot become a draft', () => {
  assert.ok(contributionProblems(guide, emptyContribution()).length >= 3)
  assert.throws(() => buildContributionDraft(guide, emptyContribution()))
})
test('draft keeps unrun tests and unverified provenance visible', () => {
  const draft = buildContributionDraft(guide, input())
  assert.match(draft, /未运行测试/)
  assert.match(draft, /未提交/)
  assert.match(draft, /未核对工作区/)
  assert.doesNotMatch(draft, /Fixes #3|Closes #3/)
})
test('failed test records cannot be rewritten into success', () => {
  const f = { ...input(), testStatus: 'failed', testCommand: 'python -m pytest tests', testExitCode: '1', testOutput: '6 failed, 625 passed, 3 skipped, 1 xfailed' }
  const draft = buildContributionDraft(guide, f)
  assert.match(draft, /测试失败，仍待处理/)
  assert.match(draft, /6 failed, 625 passed/)
  f.testStatus = 'passed'
  assert.throws(() => buildContributionDraft(guide, f), /状态与退出码不一致/)
})
test('claimed success requires actual command exit code and output fields', () => {
  assert.throws(() => buildContributionDraft(guide, { ...input(), testStatus: 'passed' }))
  const f = { ...input(), testStatus: 'passed', testCommand: 'pytest', testExitCode: '0', testOutput: '24 passed; subset only' }
  assert.match(buildContributionDraft(guide, f), /未经工具执行验证/)
  assert.match(buildContributionDraft(guide, f), /subset only/)
})
test('task links cannot silently point at another repository or script', () => {
  for (const issueUrl of ['https://github.com/other/r/issues/3', 'javascript:alert(1)', 'https://github.com/o/r/issues/3/fake', 'https://user:pass@github.com/o/r/issues/3']) {
    assert.throws(() => buildContributionDraft(guide, { ...input(), issueUrl }))
  }
})
test('manual tasks remain possible with their provenance retained', () => {
  assert.match(buildContributionDraft(guide, { ...input(), issueUrl: '' }), /人工选题/)
})
test('guide reference and actual change base cannot be silently conflated', () => {
  const f = { ...input(), baseRevision: 'b'.repeat(40) }
  const draft = buildContributionDraft(guide, f)
  assert.match(draft, /版本不同/)
  assert.ok(draft.includes('b'.repeat(40)))
  assert.throws(() => buildContributionDraft(guide, { ...input(), baseRevision: 'main' }), /40 位/)
})
test('actual pasted diff takes precedence over typed paths', () => {
  const f = { ...input(), patch: 'diff --git a/docs/a.rst b/docs/a.rst\n--- a/docs/a.rst\n+++ b/docs/a.rst\n@@ -1 +1 @@\n-old\n+new\n' }
  assert.deepEqual(changedFiles(f), ['docs/a.rst'])
  assert.match(buildContributionDraft(guide, f), /从用户粘贴的 diff 解析/)
  f.patch = 'diff --git a/../../outside b/../../outside\n@@ -1 +1 @@\n-x\n+y'
  assert.throws(() => buildContributionDraft(guide, f), /相对路径/)
  f.patch = 'diff --git a/a.txt b/a.txt'
  assert.throws(() => buildContributionDraft(guide, f), /缺少变更内容/)
})
