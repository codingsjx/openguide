import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/types/learningProgress.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { emptyExecution, executionProblems, updateLearningRecord, emptyLearningProgress, learningIdentity, progressKey, loadLearningProgress, saveLearningProgress, pendingPrerequisites, nextLearningAction, learningMarkdown, rememberLearningGuide, lastLearningGuide } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

const guide = () => ({ repo_url: 'https://github.com/o/r', default_branch: 'a'.repeat(40), steps: [
  { step_id: 1, stage: 'A', title: 'Install dependencies', command: 'uv sync', working_directory: 'backend', evidence: { kind: 'file', source: 'backend/README.md', quote: 'uv sync' }, expected: 'Check installation' },
  { step_id: 2, stage: 'B', title: 'Run tests', command: 'uv run pytest tests/ -q', working_directory: 'backend', evidence: { kind: 'file', source: 'backend/README.md', quote: 'uv run pytest tests/ -q' }, expected: 'Record output', prerequisite_step_ids: [1] },
] })
const memory = () => { const values = new Map(); return { values, getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }

test('returning to the same guide restores the current step and manual notes', () => {
  const g = guide(), store = memory(), p = emptyLearningProgress(g)
  p.currentStepId = 2; p.records['1'] = { status: 'done', note: 'Dependencies prepared in backend' }
  assert.equal(saveLearningProgress(p, store), true)
  assert.deepEqual(loadLearningProgress(g, store), p)
  assert.deepEqual(loadLearningProgress({ ...g, is_saved: true }, store), p)
})

test('completion never migrates to a different repo, revision, command or directory', () => {
  const g = guide(), store = memory(), p = emptyLearningProgress(g)
  p.records['1'] = { status: 'done', note: 'old result' }; saveLearningProgress(p, store)
  for (const changed of [
    { ...g, repo_url: 'https://github.com/other/r' },
    { ...g, is_demo: true },
    { ...g, default_branch: 'b'.repeat(40) },
    { ...g, steps: g.steps.map((s) => ({ ...s, command: s.command + ' --new-option' })) },
    { ...g, steps: g.steps.map((s) => ({ ...s, working_directory: 'frontend' })) },
  ]) assert.deepEqual(loadLearningProgress(changed, store).records, {})
})

test('storage-key collision cannot reuse records from another exact workflow', () => {
  const g = guide(), store = memory(), p = emptyLearningProgress(g)
  store.setItem(progressKey(p.identity), JSON.stringify({ ...p, identity: 'another workflow', records: { 1: { status: 'done', note: '' } } }))
  assert.deepEqual(loadLearningProgress(g, store).records, {})
})

test('blocked and deferred steps are not counted as completed prerequisites', () => {
  const g = guide(), p = emptyLearningProgress(g)
  for (const status of ['pending', 'blocked', 'skipped']) {
    p.records['1'] = { status, note: '' }
    assert.equal(pendingPrerequisites(g, g.steps[1], p).length, 1)
  }
  p.records['1'].status = 'done'
  assert.equal(pendingPrerequisites(g, g.steps[1], p).length, 0)
  assert.equal(pendingPrerequisites({ ...g, default_branch: 'b'.repeat(40) }, g.steps[1], p).length, 1)
})

test('unavailable or damaged browser storage leaves the guide usable', () => {
  const g = guide(), fail = { getItem() { throw Error('storage blocked') }, setItem() { throw Error('quota') } }
  assert.deepEqual(loadLearningProgress(g, fail).records, {})
  assert.equal(saveLearningProgress(emptyLearningProgress(g), fail), false)
  const store = memory(), key = progressKey(learningIdentity(g))
  for (const raw of ['{broken', JSON.stringify({ identity: learningIdentity(g), records: { 999: { status: 'done', note: '' } } }),
    JSON.stringify({ identity: learningIdentity(g), records: { 1: { status: 'passed', note: '' } } }),
    JSON.stringify({ identity: learningIdentity(g), records: { 1: { status: 'done', note: 'x'.repeat(1001) } } })]) {
    store.setItem(key, raw)
    assert.deepEqual(loadLearningProgress(g, store).records, {})
  }
})

test('next action prioritizes obstacles and respects offline help availability', () => {
  const g = guide(), p = emptyLearningProgress(g), s = g.steps[1]
  p.records['2'] = { status: 'blocked', note: 'missing tool' }
  assert.match(nextLearningAction(s, p, []), /脱敏日志/)
  assert.match(nextLearningAction(s, p, [], false), /本机查看/)
  p.records['2'].status = 'pending'
  assert.match(nextLearningAction(s, p, [g.steps[0]]), /第 1 步/)
  assert.match(nextLearningAction({ ...s, working_directory: null }, p, []), /先从出处确认执行目录/)
  assert.match(nextLearningAction({ ...s, missing_inputs: ['backend/tests'] }, p, []), /缺失路径/)
})

test('export distinguishes manual completion, blocked work and unexecuted commands', () => {
  const g = guide(), p = emptyLearningProgress(g)
  p.records['1'] = { status: 'done', note: 'Exit code 0; only dependency preparation checked' }
  p.records['2'] = { status: 'blocked', note: 'Tool unavailable; no tests executed' }
  const text = learningMarkdown(g, p)
  assert.match(text, /手动记录完成：1\/2/)
  assert.match(text, /未经独立核验/)
  assert.match(text, /状态：卡住了/)
  assert.match(text, /指南建议目录：backend/)
  assert.match(text, /Tool unavailable/)
  assert.match(text, /系统没有执行命令/)
  assert.match(learningMarkdown({ ...g, default_branch: 'b'.repeat(40) }, p), /手动记录完成：0\/2/)
})

test('export treats notes as literal user text rather than Markdown instructions', () => {
  const g = guide(), p = emptyLearningProgress(g)
  p.records['1'] = { status: 'blocked', note: '![image](https://example.invalid/pixel)\n<script>example</script>' }
  const text = learningMarkdown(g, p)
  assert.ok(!text.includes('![image]('))
  assert.ok(!text.includes('<script>'))
})

test('resume snapshot contains the guide but excludes unrelated logs, history and settings', () => {
  const g=guide(),store=memory()
  assert.equal(rememberLearningGuide({...g,rawLog:'private log',history:['private question'],api_key:'private key'},store),true)
  const raw=lastLearningGuide(store)
  assert.deepEqual(JSON.parse(raw).steps,g.steps)
  assert.ok(!raw.includes('private'))
  assert.equal(rememberLearningGuide({...g,is_demo:true},store),true)
  assert.equal(lastLearningGuide(store),raw)
  assert.equal(rememberLearningGuide({...g,reasons:['x'.repeat(2_000_001)]},store),false)
  assert.equal(lastLearningGuide(store),raw)
})

test('oversized progress is not reported saved when it cannot be restored', () => {
  const store=memory(),p=emptyLearningProgress(guide())
  p.identity+='x'.repeat(500_000)
  assert.equal(saveLearningProgress(p,store),false)
  assert.equal(store.values.size,0)
})

test('execution records survive note/status changes and restore without changing guide identity', () => {
  const g=guide(),p=emptyLearningProgress(g),store=memory()
  const execution={...emptyExecution(),status:'failed',command:'uv run pytest tests/unit -q',directory:'copy/backend',exitCode:'1',scope:'unit only',summary:'2 failed; integration not run'}
  p.records['2']=updateLearningRecord(undefined,{execution})
  p.records['2']=updateLearningRecord(p.records['2'],{note:'need help'})
  p.records['2']=updateLearningRecord(p.records['2'],{status:'blocked'})
  saveLearningProgress(p,store)
  assert.deepEqual(loadLearningProgress(g,store),p)
  const text=learningMarkdown(g,p)
  for(const value of ['失败','copy/backend','unit only','2 failed; integration not run','退出码：1','未经核验']) assert.ok(text.includes(value))
  assert.equal(p.records['2'].status,'blocked')
  assert.equal(p.identity,learningIdentity(g))
})

test('manual completion never fabricates an execution result; inconsistent claims stay visible', () => {
  assert.equal(updateLearningRecord(undefined,{status:'done'}).execution,undefined)
  assert.deepEqual(executionProblems(),[])
  assert.deepEqual(executionProblems({...emptyExecution(),status:'not_run'}),[])
  assert.ok(executionProblems({...emptyExecution(),status:'not_run',exitCode:'0'}).length)
  assert.ok(executionProblems({...emptyExecution(),status:'passed',exitCode:'1'}).length)
  assert.ok(executionProblems({...emptyExecution(),exitCode:'success'}).length)
  assert.deepEqual(executionProblems({...emptyExecution(),status:'passed',command:'pytest',directory:'copy/backend',scope:'unit',summary:'3 passed',exitCode:'0'}),[])
  const g=guide(),p=emptyLearningProgress(g),store=memory()
  p.records['1']={status:'pending',note:'old note',execution:{...emptyExecution(),status:'passed',exitCode:'1'}}
  saveLearningProgress(p,store)
  assert.equal(loadLearningProgress(g,store).records['1'].execution.exitCode,'1')
  assert.match(learningMarkdown(g,p),/待核对：记录通过时/)
})

test('damaged optional execution fields do not erase legacy progress and notes', () => {
  const g=guide(),p=emptyLearningProgress(g),store=memory()
  for(const execution of [null,{...emptyExecution(),status:'auto_verified'},{...emptyExecution(),summary:'x'.repeat(1001)},{...emptyExecution(),command:42}]) {
    p.records['1']={status:'done',note:'preserve',execution}
    saveLearningProgress(p,store)
    assert.deepEqual(loadLearningProgress(g,store).records['1'],{status:'done',note:'preserve'})
  }
})
