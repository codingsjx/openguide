import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const compile = (source) => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(compile(source)).toString('base64')}`
const helperUrl = moduleUrl(await readFile(new URL('../src/types/guideTimeout.ts', import.meta.url), 'utf8'))
const { guideRequestTimeoutMs, isGuideTimeout, loadGuideTimeout, saveGuideTimeout } = await import(helperUrl)
const apiSource = (await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8'))
  .replace("'../types/guideTimeout'", JSON.stringify(helperUrl)).replace('import.meta.env.VITE_API_BASE', 'undefined')
const { api } = await import(moduleUrl(apiSource))

test('extended model waits receive a matching total browser budget', () => {
  assert.equal(guideRequestTimeoutMs(25),180_000)
  assert.equal(guideRequestTimeoutMs(60),320_000)
  assert.equal(guideRequestTimeoutMs(120),560_000)
  assert.equal(guideRequestTimeoutMs(120,false),180_000)
  for (const invalid of [0,9,121,25.5,NaN,Infinity,'60',null]) assert.equal(isGuideTimeout(invalid),false)
})

test('browser preference is bounded and unavailable storage is recoverable', (t) => {
  const previous=globalThis.window
  t.after(()=>{globalThis.window=previous})
  const values=new Map()
  globalThis.window={localStorage:{getItem:(key)=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)}}
  assert.equal(loadGuideTimeout(),25)
  saveGuideTimeout(90)
  assert.equal(loadGuideTimeout(),90)
  saveGuideTimeout(999)
  assert.equal(loadGuideTimeout(),90)
  globalThis.window={get localStorage(){throw new Error('blocked')}}
  assert.equal(loadGuideTimeout(),25)
  assert.doesNotThrow(()=>saveGuideTimeout(60))
})

test('API sends the chosen timeout and keeps cancellation wired while extending the timer', async (t) => {
  const oldWindow=globalThis.window, oldFetch=globalThis.fetch
  t.after(()=>{globalThis.window=oldWindow;globalThis.fetch=oldFetch})
  const timers=[],requests=[],cleared=[]
  globalThis.window={setTimeout:(_callback,ms)=>{timers.push(ms);return timers.length},clearTimeout:(id)=>cleared.push(id)}
  globalThis.fetch=async (url,init)=>{requests.push({url,...init});return {ok:true,json:async()=>({steps:[]})}}
  const controller=new AbortController()
  await api.postGuide('https://github.com/o/r',true,controller.signal,120)
  assert.deepEqual(JSON.parse(requests[0].body),{url:'https://github.com/o/r',use_llm:true,model_timeout_s:120})
  assert.equal(timers[0],560_000)
  assert.equal(requests[0].signal.aborted,false)
  assert.deepEqual(cleared,[1])
  await api.postGuide('o/r',false,undefined,120)
  assert.equal(timers[1],180_000)
})
