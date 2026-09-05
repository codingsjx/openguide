# OpenGuide 代码大纲

**版本** v1.0
**日期** 2026-09-05
**约定**：A 主责 backend/（管线），B 主责 frontend/（UI），C 主责 benchmark/（评测与材料）。三者通过 docs/ 下的接口约定协作。

---

## 1. 顶层结构

```
openguide/
├── docs/                    # 文档
│   ├── task_book.md         # 任务书（技术方案）
│   ├── team_roles.md        # 团队分工执行表
│   └── api_contract.md      # (待建) 接口约定：Profile/GuideStep/检索/追问 schema
├── backend/                 # FastAPI 后端（A 主责）
│   ├── app/
│   │   ├── main.py          # FastAPI 入口，挂载路由
│   │   ├── config.py        # 读取 .env：GITHUB_TOKEN / LLM_API_KEY / 向量库路径
│   │   ├── api/             # HTTP 层
│   │   │   ├── routes/
│   │   │   │   ├── profile.py     # POST /api/profile
│   │   │   │   ├── guide.py       # POST /api/guide
│   │   │   │   ├── search.py      # POST /api/search
│   │   │   │   └── followup.py    # POST /api/followup
│   │   │   └── deps.py            # 依赖注入（复用缓存/客户端实例）
│   │   ├── core/            # 业务管线（四段）
│   │   │   ├── github/
│   │   │   │   ├── client.py      # GitHub API 封装 + 缓存 + 限流/未授权处理
│   │   │   │   └── models.py      # 仓库元数据/issue/文档数据模型
│   │   │   ├── profile/
│   │   │   │   ├── schema.py      # Profile Pydantic schema（§2，全局约定）
│   │   │   │   └── builder.py     # 画像构建：抓取→聚合→画像 JSON
│   │   │   ├── index/            # 模块 2：分层视角化索引
│   │   │   │   ├── perspectives.py # V1-V4 视角文档组装（内容来源路由）
│   │   │   │   ├── compress.py     # 视角压缩重写（LLM 聚合跨文件步骤）
│   │   │   │   ├── embedder.py     # sentence-transformers 封装
│   │   │   │   ├── vectorstore.py  # chromadb 封装（四索引独立 collection）
│   │   │   │   └── retrieval.py    # 分层检索：按需激活（默认 V1+V3）
│   │   │   ├── decide/
│   │   │   │   └── decider.py     # 决策树：适不适合新手 + 流程分支（纯规则，可单测）
│   │   │   ├── generate/         # 模块 3：结构化生成
│   │   │   │   ├── schemas.py     # GuideStep/Guide/Evidence Pydantic（§3，全局约定）
│   │   │   │   ├── llm.py         # OpenAI 兼容客户端封装（Key 只在 .env）
│   │   │   │   ├── prompts.py     # Stage A-D prompt 模板
│   │   │   │   ├── evidence.py    # 证据锚点校验（无证据不宣称，§4）
│   │   │   │   └── pipeline.py    # Stage A-D 编排
│   │   │   ├── followup/
│   │   │   │   ├── granular.py    # "这步太粗"：重检索 V3 出子步骤
│   │   │   │   ├── explain.py     # "看不懂为什么"：检索 V1/V2 解释原理
│   │   │   │   └── diagnose.py    # "报错了"：本地规则预判 + LLM 定位
│   │   │   └── treeparse/         # （可选加分）tree-sitter 符号表
│   │   │       └── symbols.py     # V2 升级为调用图
│   │   └── utils/
│   │       ├── cache.py           # 磁盘/内存缓存（规避 GitHub 限流）
│   │       └── logging.py
│   ├── tests/              # pytest（A 写核心，C 补评测脚本）
│   │   ├── unit/                  # decider / evidence / schema 纯逻辑
│   │   ├── integration/           # 全链路（本地 fixture 仓库）
│   │   ├── fixtures/
│   │   │   └── repos/             # 本地小仓库样例（供 L1 烟测，不宣称质量）
│   │   └── conftest.py
│   ├── requirements.txt           # 依赖锁定
│   ├── .env.example               # 不含真实 Key
│   └── Dockerfile
├── frontend/               # React + Vite + antd（B 主责）
│   ├── src/
│   │   ├── main.tsx / App.tsx     # 路由（Home / Profile / Guide）
│   │   ├── api/
│   │   │   └── client.ts          # fetch 封装（对应 §5 API）
│   │   ├── pages/
│   │   │   ├── HomePage.tsx       # 输入仓库 URL
│   │   │   ├── ProfilePage.tsx    # 体检卡（画像 JSON 渲染）
│   │   │   └── GuidePage.tsx      # 向导分步主流程
│   │   ├── components/
│   │   │   ├── Wizard/            # 向导容器：步骤态管理、第 n/4 前进逻辑
│   │   │   ├── GuideStep/         # Step 卡片渲染（command/expected/fail_hints）
│   │   │   ├── EvidencePanel/     # 证据面板：当前步骤引用实时亮起 + 原始出处跳转
│   │   │   ├── FollowupBar/       # 三步追问入口 + 会话
│   │   │   ├── ProfileCard/       # 体检卡可视化（语言/license/gfi/活跃度）
│   │   │   └── CodeBlock/         # 命令块 + 复制按钮
│   │   ├── types/                 # 前端 TS 类型（镜像后端 schema）
│   │   │   ├── profile.ts
│   │   │   └── guide.ts
│   │   ├── hooks/                 # useGuide / useFollowup 等
│   │   └── styles/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   └── Dockerfile
├── benchmark/              # 评测与材料（C 主责）
│   ├── runner.py           # 评测运行器：scraper/索引/生成/证据校验 脚本化后端
│   ├── golden/
│   │   ├── repos.json            # 3-5 个 golden 仓库清单
│   │   └── golden_guides/        # 人工标准上手指南（L2 标注，jsonl）
│   ├── l1_smoke.py         # L1 烟测（固定本地仓库，只验链路）
│   ├── l2_golden.py        # L2 黄金评估（步骤完整率/命令可执行率/证据命中率）
│   ├── l3_ablation.py      # L3 消融（朴素 baseline vs 分层管线，同仓库同基准）
│   ├── l4_contribution.py  # L4 真实 PR 记录（链接/commit）
│   ├── reports/            # 输出 jsonl + 汇总报告（提交包证据）
│   └── README.md           # 评测口径：只报人工复核集，样例不宣称质量
├── docker-compose.yml      # backend + frontend + (可选)embedding 缓存卷
├── .env.example            # 顶层示例（backend/.env.example 同步）
├── .gitignore              # 排除 .env、chroma 数据、node_modules、评测临时产物
└── README.md               # 作品说明 + 冷启动步骤（评审入口）
```

---

## 2. 全局约定一：Profile schema（A 定稿，B/C 依赖）

`backend/app/core/profile/schema.py`

```python
class Profile(BaseModel):
    owner: str                      # GitHub owner
    repo: str
    languages: dict[str, float]     # {"python": 0.72, ...}
    stars: int
    license: str | None             # "Apache-2.0"
    has_docs: bool                  # README + CONTRIBUTING + docs/ 齐全
    build: BuildInfo | None         # tool / package_manager / test_cmd
    has_gfi: GfiInfo                # count / oldest_days
    activity: ActivityInfo          # commits_30d / last_release_days
    suitability: str                # decider 输出："promising"/"unclear"/"avoid"
    reasons: list[str]              # 决策理由（前端展示为体检卡"建议"）
```

对应前端 `ProfileCard`：语言占比 → 环形图；stars/gfi → 数字卡；suitability → 醒目状态。

---

## 3. 全局约定二：Guide schema（A 定稿，B/C 依赖）

`backend/app/core/generate/schemas.py`

```python
class Evidence(BaseModel):
    kind: Literal["file", "issue", "missing"]
    source: str             # "CONTRIBUTING.md#L22" 或 issue 链接
    quote: str              # 原文摘录

class GuideStep(BaseModel):
    step_id: int
    stage: str              # "A 环境搭建" / "B 测试基线" / "C 选 issue" / "D 首 PR"
    title: str
    command: str | None     # 无可执行命令则为 None（如"阅读 X 文件"）
    expected: str           # 期望结果/判定标准（"看到 42 passed"）
    fail_hints: list[str]
    evidence: Evidence      # 无来源 → kind="missing" + 提示去 issue 问

class Guide(BaseModel):
    repo_url: str
    stages: list[GuideStep]
    unsuitable: bool | None # 决策树判"不适合"时为 True + reasons
```

---

## 4. 铁律落点：evidence.py（无证据不宣称）

职责：
- 生成后对每条 `GuideStep` 做**证据校验**：`evidence.source` 必须能回溯到抓取缓存里的真实文件/行号/issue；
- 校验失败 → 降级为 `kind="missing"`，并附"该项目文档缺失，建议去 issue #xx 询问"；
- 供 benchmark L2 的"证据命中率"指标直接复用此校验函数（**评测与生成共用同一实现**，防口径漂移）。

---

## 5. HTTP API 一览（前后端接口约定）

| 方法 | 路径 | 请求 | 响应 | 对应管线 |
|---|---|---|---|---|
| POST | `/api/profile` | `{url}` | Profile | 画像（含决策建议） |
| POST | `/api/guide` | `{url}` | Guide | 画像→索引→决策→生成 |
| POST | `/api/search` | `{url, perspective, query}` | `[{chunk, source}]` | 分层检索（追问/证据用） |
| POST | `/api/followup` | `{url, step_id, kind, log?}` | 追加 GuideStep / 解释 / 诊断 | 三步追问 |

`kind ∈ {granular, explain, diagnose}`，`log` 仅 diagnose 需要。

---

## 6. 四段管线的代码路径（数据流）

```
POST /api/profile
  → github/client.py（带缓存）
  → profile/builder.py → Profile
  → decide/decider.py → suitability + reasons
  → 返回前端体检卡

POST /api/guide
  → profile/builder.py（画像，可复用缓存）
  → index/perspectives.py 组装 V1-V4 原文视角
  → index/compress.py LLM 压缩重写 → embedder.py → vectorstore.py（四 collection）
  → decide/decider.py 判适合性
  → generate/pipeline.py 按 Stage A-D：
       每 Stage：index/retrieval.py 检索对应视角 → prompts.py → llm.py → schemas.py 校验
       → generate/evidence.py 证据校验 → GuideStep
  → 返回 Guide

POST /api/followup（kind=granular/explain/diagnose）
  → followup/*.py 重新检索 / 本地规则 + LLM → 追加步骤/解释/诊断
```

---

## 7. 与分工的映射速查

| 你想改的模块 | 改哪个文件 | 主要责任 |
|---|---|---|
| GitHub 抓取/画像 | `backend/app/core/github/`, `profile/` | A |
| 索引/检索 | `backend/app/core/index/` | A |
| 决策树/生成/证据 | `backend/app/core/decide/`, `generate/` | A |
| 后端路由薄接口 | `backend/app/api/routes/` | A（B 可协助） |
| UI 页面/组件 | `frontend/src/pages/`, `components/` | B |
| 前后端对接类型 | `frontend/src/types/`, `api/client.ts` | B |
| 评测运行器 | `benchmark/runner.py`, `l1_l4` | C |
| 黄金标注 | `benchmark/golden/` | C |
| 集成测试 fixture | `backend/tests/fixtures/repos/` | C（初选），A（跑通） |

---

## 8. 待建/先行项（开工顺序建议）

1. `docs/api_contract.md`——A 先定稿 Profile + GuideStep 字段（§2/§3），B/C 才能并行；
2. `backend/` 骨架 + `github/client.py` + `profile/schema.py`（M0）；
3. `frontend/` 骨架 + ProfilePage 体检卡（M0，依赖 2 的 mock 数据可先行）；
4. `benchmark/golden/repos.json` 初选（M0，C 手工选库）。
