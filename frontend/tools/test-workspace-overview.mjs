import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source=await readFile(new URL('../src/types/workspaceOverview.ts',import.meta.url),'utf8')
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}})
const {workspaceOverview}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const profile={owner:'o',repo:'r',default_branch:'master',description:'Repository description',languages:{Python:0.8,TypeScript:0.2},has_readme:true}
const base={loading:false,demo:false,profile,guide:null,url:'https://github.com/o/r'}

test('loading never claims metadata has arrived or exposes URL query secrets',()=>{
  const result=workspaceOverview({...base,loading:true,url:'https://github.com/other/new'})
  assert.equal(result.tone,'loading')
  assert.equal(result.repository,'other/new')
  assert.deepEqual(result.facts,[])
  const noProfile=workspaceOverview({...base,loading:true,profile:null,url:'https://github.com/o/r?token=private'})
  assert.equal(noProfile.repository,'正在连接仓库')
})
test('saved and sample views never inherit a previous repository profile',()=>{
  const saved=workspaceOverview({...base,guide:{repo_url:'https://github.com/other/saved',default_branch:'a'.repeat(40)}})
  assert.equal(saved.repository,'other/saved')
  assert.equal(saved.tone,'saved')
  assert.ok(!saved.facts.some((f)=>f.includes('Python')))
  const demo=workspaceOverview({...base,demo:true,url:'https://github.com/psf/requests'})
  assert.equal(demo.repository,'psf/requests')
  assert.equal(demo.tone,'demo')
  assert.deepEqual(demo.facts,['示例浏览'])
})
test('partial collection keeps unavailable languages and root signals out of facts',()=>{
  const result=workspaceOverview({...base,profile:{...profile,unavailable_signals:['languages','root']}})
  assert.equal(result.tone,'partial')
  assert.deepEqual(result.facts,['默认分支 master'])
  assert.match(result.status,/待确认/)
  const ready=workspaceOverview(base)
  assert.equal(ready.repository,'o/r')
  assert.equal(ready.description,'Repository description')
  assert.deepEqual(ready.facts,['默认分支 master','Python · TypeScript','README 入口'])
})
