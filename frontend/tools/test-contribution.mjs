import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/types/contribution.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { emptyContribution, contributionProblems, buildContributionDraft, changedFiles, contributionPreparationJson, parseContributionPreparation, referencedExecutions, taskExplorationEntries } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const guide = { repo_url: 'https://github.com/o/r', default_branch: 'a'.repeat(40), steps: [] }
const input = () => ({ ...emptyContribution(), task: 'Document prerequisites', issueUrl: guide.repo_url + '/issues/3', problem: 'Instructions omit a prerequisite', acceptance: 'The documented prerequisite matches the actual setup requirement', changeSummary: 'Added the prerequisite', files: 'CONTRIBUTING.md', testDirectory: 'backend', testScope: 'related tests only' })

test('a direction or plan never substitutes for actual change and verification', () => {
  const f = { ...emptyContribution(), kind: 'bug', task: 'Investigate a failure', problem: 'Reproduction is still pending', acceptance: 'The same reproducer succeeds after the fix' }
  assert.throws(() => buildContributionDraft(guide, f), /尚未修改/)
  assert.throws(() => buildContributionDraft(guide, { ...input(), acceptance: '' }), /验收标准/)
})

test('pre-change observations and later verification remain separate in a draft', () => {
  const f = { ...input(), baselineNotes: 'Original version failed at step 2', verificationNotes: 'Earlier environment check passed; subset only' }
  const draft = buildContributionDraft(guide, f)
  assert.match(draft, /本次改动未运行测试/)
  assert.match(draft, /不能代替本次改动后的验证/)
  assert.match(draft, /Original version failed/)
  assert.match(draft, /验收标准（计划/)
})

test('manual completion creates no execution reference; failures retain exact details', () => {
  const g = { ...guide, steps: [{ step_id: 1, title: 'Test backend' }] }
  assert.equal(referencedExecutions(g, { 1: { status: 'done', note: 'read' } }), '')
  const failed = { status: 'failed', command: 'pytest tests/unit -q', directory: 'backend', scope: 'one subset', exitCode: '1', summary: '2 failed; full suite not run' }
  const text = referencedExecutions(g, { 1: { status: 'done', note: '', execution: failed } })
  assert.match(text, /用户记录失败/)
  assert.match(text, /2 failed; full suite not run/)
  assert.ok(text.includes(guide.default_branch))
  assert.doesNotMatch(text, /用户记录通过/)
})

test('legacy preparations import without inventing acceptance criteria or execution scope', () => {
  const raw = JSON.parse(contributionPreparationJson(guide, input()))
  delete raw.input.acceptance; delete raw.input.testScope; delete raw.input.kind
  const restored = parseContributionPreparation(JSON.stringify(raw), guide).input
  assert.equal(restored.kind, 'unspecified')
  assert.equal(restored.acceptance, '')
  assert.equal(restored.testScope, '')
  assert.ok(contributionProblems(guide, restored).some(p => p.includes('验收标准')))
})

test('successful post-change records require the actual directory and tested scope', () => {
  const f = { ...input(), testStatus: 'passed', testCommand: 'pytest tests -q', testExitCode: '0', testOutput: '8 passed' }
  assert.throws(() => buildContributionDraft(guide, { ...f, testDirectory: '' }), /目录、范围/)
  assert.throws(() => buildContributionDraft(guide, { ...f, testScope: '' }), /目录、范围/)
  assert.match(buildContributionDraft(guide, f), /验证范围：related tests only/)
})

test('task-card observations round-trip but invalid task kinds are rejected', () => {
  const f = { ...input(), kind: 'tests', outOfScope: 'No unrelated components', baselineNotes: 'Existing behavior reproduced' }
  const raw = contributionPreparationJson(guide, f)
  assert.deepEqual(parseContributionPreparation(raw, guide).input, f)
  const changed = JSON.parse(raw); changed.input.kind = 'already_merged'
  assert.throws(() => parseContributionPreparation(JSON.stringify(changed), guide), /任务方向/)
})

test('exploration reuses exact verified test operations and source lines', () => {
  const g = { ...guide, steps: [{ step_id: 2, stage: 'B', title: 'Backend', command: 'uv run pytest tests/ -q', working_directory: 'backend', evidence: { kind: 'file', source: 'backend/README.md', verification: 'command_verified', line_start: 12 } }] }
  const entries = taskExplorationEntries(g, 'tests')
  assert.equal(entries.length, 1)
  assert.equal(entries[0].command, g.steps[0].command)
  assert.equal(entries[0].directory, 'backend')
  assert.equal(entries[0].href, guide.repo_url+'/blob/'+guide.default_branch+'/backend/README.md#L12')
})

test('exploration never invents tests from file existence, guessed paths or mutable refs', () => {
  const g = { ...guide, steps: [{ step_id: 1, stage: 'B', command: 'pytest fabricated', evidence: { kind: 'file', source: 'README.md', verification: 'source_exists' } }] }
  assert.deepEqual(taskExplorationEntries(g, 'bug'), [])
  g.steps[0].evidence.verification = 'command_verified'; g.steps[0].evidence.source = '../../other.md'
  assert.deepEqual(taskExplorationEntries(g, 'bug'), [])
  g.steps[0].evidence.source = 'README.md'; g.default_branch = 'main'
  assert.deepEqual(taskExplorationEntries(g, 'bug'), [])
})

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

test('unfinished task preparation round-trips without becoming a PR draft', () => {
  const partial={...emptyContribution(),task:'Investigate missing setup step',problem:'No change made yet'}
  const restored=parseContributionPreparation(contributionPreparationJson(guide,partial),guide)
  assert.deepEqual(restored.input,partial)
  assert.equal(restored.referenceRevision,guide.default_branch)
  assert.throws(()=>buildContributionDraft(guide,restored.input),/尚未修改/)
})

test('preparation cannot be applied to another repository or an external host', () => {
  const raw=contributionPreparationJson(guide,input())
  assert.throws(()=>parseContributionPreparation(raw,{...guide,repo_url:'https://github.com/other/r'}),/其他仓库/)
  const payload=JSON.parse(raw)
  for(const repo_url of ['https://example.invalid/o/r','https://user:pass@github.com/o/r','javascript:alert(1)']) {
    assert.throws(()=>parseContributionPreparation(JSON.stringify({...payload,repo_url}),guide),/其他仓库/)
  }
  assert.equal(parseContributionPreparation(raw,{...guide,repo_url:'https://github.com/O/R/'}).input.task,input().task)
})

test('invalid preparation shapes are rejected and unrelated fields are never restored', () => {
  const payload=JSON.parse(contributionPreparationJson(guide,input()))
  for(const change of [{input:null},{input:[]},{input:{task:{text:'x'}}},{input:{task:null}},{input:{testStatus:'verified'}},{reference_revision:'line\nbreak'}]) {
    assert.throws(()=>parseContributionPreparation(JSON.stringify({...payload,...change}),guide))
  }
  assert.throws(()=>parseContributionPreparation('{broken',guide),/有效 JSON/)
  assert.throws(()=>parseContributionPreparation(JSON.stringify(guide),guide),/不是贡献准备记录/)
  const restored=parseContributionPreparation(JSON.stringify({...payload,input:{...payload.input,api_key:'not-a-real-key',is_verified:true}}),guide)
  assert.equal(restored.input.api_key,undefined)
  assert.equal(restored.input.is_verified,undefined)
})

test('restored test failure or inconsistent success remains unverified and unchanged', () => {
  const failed={...input(),testStatus:'failed',testCommand:'pytest',testExitCode:'1',testOutput:'Synthetic failure; no command executed by this test'}
  const r=parseContributionPreparation(contributionPreparationJson(guide,failed),guide)
  assert.deepEqual(r.input,failed)
  assert.match(buildContributionDraft(guide,r.input),/测试失败，仍待处理/)
  const wrong=parseContributionPreparation(contributionPreparationJson(guide,{...failed,testStatus:'passed'}),guide)
  assert.throws(()=>buildContributionDraft(guide,wrong.input),/状态与退出码不一致/)
})

test('changed guide revision remains visible in restored records and regenerated drafts', () => {
  const current={...guide,default_branch:'b'.repeat(40)}
  const restored=parseContributionPreparation(contributionPreparationJson(guide,input()),current)
  const draft=buildContributionDraft(current,restored.input,restored.referenceRevision)
  assert.match(draft,/准备记录与当前指南版本不同/)
  assert.ok(draft.includes(guide.default_branch)&&draft.includes(current.default_branch))
  assert.equal(JSON.parse(contributionPreparationJson(current,restored.input,restored.referenceRevision)).reference_revision,guide.default_branch)
})

test('backup size limits account for actual serialized bytes and unsafe revision text', () => {
  assert.throws(()=>contributionPreparationJson(guide,{...input(),patch:'"'.repeat(1_000_000)}),/超过 2 MB/)
  assert.throws(()=>parseContributionPreparation('x'.repeat(2_000_001),guide),/超过 2 MB/)
  assert.throws(()=>contributionPreparationJson(guide,input(),'bad\nrevision'),/参考版本无效/)
})
