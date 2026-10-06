# OpenGuide 代码大纲

**版本** v1.0
**日期** 2026-09-05
**约定**：A 主责 backend/（管线），B 主责 frontend/（UI），C 主责 benchmark/（评测与材料）。三者通过 docs/ 下的接口约定协作。

---

## 1. 顶层结构

```
openguide/
├── docs/                       # 文档
│   ├── task_book.md            # 任务书（选题论证 / 技术方案 / 里程碑）
│   ├── team_roles.md           # 团队分工执行表
│   ├── code_outline.md         # 本文件：代码大纲与接口约定
│   ├── demo_script.md          # 现场演示脚本（3 个真实仓库 + 兜底）
│   ├── third_party_disclosure.md  # 第三方资源与许可披露
│   └── changelog.md            # 变更记录（修复与验证口径）
├── backend/                    # FastAPI 后端（A 主责）
│   ├── src/backend/
│   │   ├── config.py           # 读取 .env：GITHUB_TOKEN / LLM_* / 向量库路径
│   │   ├── api/
│   │   │   ├── main.py         # FastAPI 入口，挂载路由 + CORS
│   │   │   └── routes/
│   │   │       ├── profile.py  # POST /api/profile
│   │   │       ├── search.py   # POST /api/search
│   │   │       ├── guide.py    # POST /api/guide
│   │   │       ├── followup.py # POST /api/followup
│   │   │       └── settings.py # GET/POST /api/llm-config
│   │   ├── core/
│   │   │   ├── github/         # 仓库勘探（M0）
│   │   │   │   ├── client.py   # GitHub API 封装 + 磁盘缓存 + 限流处理
│   │   │   │   ├── recon.py    # 信号采集 + 文档/文件树深度抓取
│   │   │   │   ├── models.py   # RepoMeta / DocFile
│   │   │   │   └── parse.py    # URL → (owner, repo)
│   │   │   ├── profile/        # 画像 schema 与构建
│   │   │   │   ├── schema.py   # Profile（§2 全局约定）
│   │   │   │   ├── builder.py  # RawSignals → Profile
│   │   │   │   └── service.py  # URL → Profile
│   │   │   ├── index/          # 四视角分层索引（M1，技术差异点核心）
│   │   │   │   ├── perspectives.py # V1-V4 视角文档组装
│   │   │   │   ├── embedder.py     # 嵌入模型封装
│   │   │   │   ├── vectorstore.py  # 向量库封装 + 确定性回退检索
│   │   │   │   ├── retrieval.py    # 意图 → 视角路由
│   │   │   │   └── service.py      # RepoIndex（索引 + 检索入口）
│   │   │   ├── decide/
│   │   │   │   └── decider.py  # 决策树：适不适合新手（纯规则，可单测）
│   │   │   ├── generate/       # 结构化生成（M2）
│   │   │   │   ├── schemas.py  # Guide/GuideStep/Evidence（§3 全局约定）
│   │   │   │   ├── llm.py      # [OI] 兼容客户端 + 会话内配置
│   │   │   │   ├── prompts.py  # Stage A-D prompt 模板
│   │   │   │   ├── evidence.py # 证据锚点校验（无证据不宣称）
│   │   │   │   └── pipeline.py # Stage A-D 编排 + 启发式回退
│   │   │   ├── followup/
│   │   │   │   └── service.py  # 三步追问：granular / explain / diagnose
│   │   │   └── treeparse/      # （预留）tree-sitter 符号表
│   │   └── utils/cache.py      # 磁盘缓存（规避 GitHub 限流）
│   ├── tests/                  # pytest（默认离线、无密钥）
│   ├── pyproject.toml / uv.lock
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   # React + Vite + antd（B 主责）
│   ├── src/
│   │   ├── App.tsx / main.tsx
│   │   ├── api/client.ts       # fetch 封装（对应 §5 API）
│   │   ├── pages/
│   │   │   ├── HomePage.tsx    # 首页：地址输入 + 结果标签页
│   │   │   └── GuidePage.tsx   # 贡献问答检索
│   │   ├── components/
│   │   │   ├── ProfileCard/    # 体检卡（语言/构建/gfi/活跃度）
│   │   │   ├── GuideGenerator/ # 生成贡献指南（AI / 本地规则）
│   │   │   ├── GuideWizard/    # 分步向导 + 三步追问 + 证据面板
│   │   │   └── LlmSettings/    # 会话内 LLM 配置
│   │   └── types/              # profile.ts / guide.ts（镜像后端 schema）
│   ├── package.json / pnpm-lock.yaml
│   ├── vite.config.ts
│   ├── Dockerfile / nginx.conf
│   └── index.html
├── benchmark/                  # 评测与材料（C 主责）
│   ├── golden/                 # golden 仓库清单 + 人工标准指南
│   ├── l1_smoke.py             # L1 链路烟测（不产出质量数字）
│   ├── l2_golden/runner.py     # L2 黄金评估
│   ├── l3_ablation/            # L3 消融（naive baseline vs 分层管线）
│   ├── l4_contribution/        # L4 真实贡献记录
│   ├── metrics.py / report.py  # 指标定义与报告落盘
│   └── README.md               # 评测口径（只报人工复核集）
├── docker-compose.yml          # backend + frontend 一键部署
├── .env.example                # 顶层示例（与 backend/.env.example 同步）
├── .github/workflows/ci.yml    # CI：后端测试 / 前端构建 / 密钥扫描
└── README.md                   # 作品说明 + 冷启动步骤（评审入口）
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
