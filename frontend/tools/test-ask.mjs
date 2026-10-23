import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source=await readFile(new URL('../src/types/ask.ts',import.meta.url),'utf8')
const { outputText }=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}})
const { questionsForRequest,safeSourceHref,conversationMarkdown }=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const result=()=>({repo_url:'https://github.com/o/r',question:'测试？',resolved_question:'测试？',context_used:false,revision:'a'.repeat(40),intents:['test'],status:'answered',mode:'extractive',points:[{text:'已找到测试入口',citations:['S1']}],commands:[{command:'pytest tests',citation:'S1'}],sources:[],missing:[],next_actions:['核对原文'],warnings:[],links:[]})

test('context is bounded and never crosses repositories',()=>{
  const turns=Array.from({length:7},(_,i)=>({id:i+1,question:'q'+i,result:result()}))
  turns.push({id:8,question:'other repo private question',result:{...result(),repo_url:'https://github.com/other/r'}})
  assert.deepEqual(questionsForRequest(turns,'o/r'),['q3','q4','q5','q6'])
  assert.deepEqual(questionsForRequest(turns,'https://github.com/o/r.git/'),['q3','q4','q5','q6'])
})
test('source links must match repository and fixed revision',()=>{
  const r=result(); const s={kind:'file',url:`https://github.com/o/r/blob/${r.revision}/Makefile#L1-L4`}
  assert.equal(safeSourceHref(r,s),s.url)
  for(const url of ['javascript:alert(1)','https://github.com/other/r/blob/'+r.revision+'/x','https://github.com/o/r/blob/main/Makefile']) assert.equal(safeSourceHref(r,{...s,url}),undefined)
  assert.equal(safeSourceHref(r,{kind:'issue',url:'https://github.com/o/r/issues/3'}),'https://github.com/o/r/issues/3')
})
test('download keeps provenance and missing information rather than claiming execution',()=>{
  const r=result(); r.missing=['仅运行了局部范围，其他测试未验证']; r.sources=[{id:'S1',kind:'file',source:'Makefile',url:`https://github.com/o/r/blob/${r.revision}/Makefile#L1`}]
  const text=conversationMarkdown([{id:1,question:'测试怎么运行？',result:r}])
  assert.match(text,/未执行/)
  assert.match(text,/局部范围/)
  assert.ok(text.includes(r.revision))
  assert.match(text,/Makefile/)
})

test('download preserves working directory and the actual question wait setting',()=>{
  const r=result();r.commands=[{command:'uv run pytest tests/ -q',citation:'S1',working_directory:'backend',directory_basis:'document_context'}]
  const text=conversationMarkdown([{id:1,question:'后端测试？',result:r,modelTimeoutSeconds:60}])
  assert.match(text,/执行位置（静态推导）：backend/)
  assert.match(text,/等待设置：60 秒/)
})
