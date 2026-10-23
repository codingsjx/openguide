# OpenGuide · 开源项目新手贡献智能向导

[![CI](https://github.com/codingsjx/openguide/actions/workflows/ci.yml/badge.svg)](https://github.com/codingsjx/openguide/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

输入一个 GitHub 仓库 URL，OpenGuide 从实际取得的资料生成**带原文证据、可逐步核对**的新手贡献路线图：环境怎么搭、测试怎么跑、issue 如何筛选、PR 如何准备。资料缺失时明确待确认，不保证自动完成贡献。

> 证据分级：分别显示来源存在、引用原文匹配、命令原文匹配；未通过原文核验的命令隐藏。原文匹配不代表命令已执行或建议语义正确。当前验收与待补证据见 [国赛完善记录](docs/competition_readiness.md)。

在线生成按阶段回退：某一阶段失败时保留其他阶段的 AI 输出，并标明各阶段来源；规则模式同样保留四阶段入口，资料不足时待确认。严格模型实验禁止回退。[实现与验证范围](docs/stage_fallback_20261021.md)。

任务选择与贡献准备：标签候选不足时，额外采样最多 30 个开放 issue；普通 issue 仅供浏览，不计为新手标签任务。页面分别说明无结果、采集失败及候选受阻，并提供 GitHub 检索入口。贡献工作台将选定任务、用户记录的实际改动/可选 diff、测试状态整理为本机 Markdown PR 草稿，保留失败和未运行项；不会自动提交到上游，用户记录与 diff 来源未经独立核验。

报错帮助区分本地证书路径、证书信任和网络超时，并将通用只读检查与仓库原文证据分开展示。Python 环境提示支持直接使用虚拟环境解释器；浏览步骤可以选择“仅查看下一步”，不必标记完成。[本轮修复与验收](docs/novice_recovery_20261022.md)。

生成结果会区分手动规则模式与逐阶段 AI 回退，并展示已记录的原因。资料采集失败保持醒目，版本及环境说明可展开查看；旧指南不会被猜测为手动选择。[提示分层与实测记录](docs/status_clarity_20261022.md)。

贡献问答支持中文解读、带行号的固定版本出处、同仓库连续追问、资料不足引导和记录下载。命令单独匹配原文，未通过核验的 AI 解读回退为原文整理；引用匹配不代表语义已独立复核。[问答功能及验证边界](docs/repository_qa_20261022.md)。

入门流程支持子项目构建配置清单、带出处的运行时要求，以及“开始前核对 → 原文操作 → 结果检查”的步骤细化。通用 Git 起步与 PR 准备清单单独标为工具提示；体检不再仅凭配置文件名推测包管理器或测试命令。问答可独立选择 25–120 秒的模型等待时间，下载记录保留执行目录和本轮设置。验证记录见 [入门流程补齐](output/qa/onboarding-completion-20261023/README.md)。

持续辅导支持阶段目标、前置步骤跳转、卡住/暂缓状态、本步摘要和学习记录导出。记录与指南快照仅保存在当前浏览器；刷新后可从首页继续原指南，不把其他仓库、版本或不同步骤的完成标记带入。原始排错日志、问答历史和贡献工作台表单不纳入该自动保存。首页可先选择 AI 生成或快速原文整理，手动进度不代表系统验证结果。[学习流程验收](output/qa/learning-flow-20261023/README.md)。

## 四段管线

| 阶段 | 模块 | 做什么 |
|---|---|---|
| M0 仓库勘探 | `core/github/` | 只抓决策相关信号（语言占比、构建面、gfi、活跃度、协议），输出固定 schema 画像 |
| M1 分层索引 | `core/index/` | 按**新手阅读路径**把仓库重组为四视角并各自建索引：V1 入口约定 / V2 架构地图 / V3 可执行路径 / V4 issue 槽位 |
| M2 结构化生成 | `core/generate/` | 画像驱动决策树 → Stage A–D 分阶段检索 + schema 约束生成 + 证据锚点校验 |
| M3 分步引导 | `frontend/GuideWizard` | 向导卡片流（第 n/4 步）+ 三步追问（这步太粗 / 看不懂为什么 / 报错了）+ 常驻证据面板 |

**为什么不是「clone 全文 → LLM 写总结」**：规模失配（数千文件塞不进上下文）、信息类型失配（「如何搭环境」分散在 README/CONTRIBUTING/docs/workflow 里）、能力前提失配（新手卡住不会定位问题，指南必须带预期结果与失败分支）。四视角重组正是针对这三点。

## 一键部署（Docker Compose，评审冷启动推荐）

```bash
cp .env.example .env          # 可选：填 GITHUB_TOKEN / LLM_API_KEY；不填也能跑
docker compose up --build
```

浏览器打开 http://127.0.0.1:5173 即可。前端由 nginx 提供静态站点并把 `/api`
反向代理到后端容器（同源，无需 CORS / 额外配置）。

- 默认 `USE_CHROMA=false`：走**确定性检索**，核心安装不包含向量库或模型依赖。
  Docker 启用向量检索时，在 `.env` 同时设 `INSTALL_VECTOR=true` 和 `USE_CHROMA=true` 后重新构建；首次使用会下载模型。
- 向量库与 GitHub 响应缓存挂在命名卷上，重启不丢、不重抓。
- 详细演示流程见 [docs/demo_script.md](docs/demo_script.md)。

---

## 本机运行（后端）

需先装 [uv](https://docs.astral.sh/uv/)（本项目用 uv 管理 Python 3.12）。

```bash
cd backend
uv sync                        # 按 uv.lock 安装依赖
uv run pytest tests/ -q        # 测试数量以当前运行记录为准（另运行 benchmark/tests）
uv run uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

默认依赖不安装 Chroma 和 sentence-transformers。需要向量功能时先运行
`uv sync --extra vector`，再配置 `USE_CHROMA=true`；后续运行也使用
`uv run --extra vector uvicorn backend.api.main:app --host 127.0.0.1 --port 8000`。

可选：`backend/.env`（复制 `.env.example`）填 `GITHUB_TOKEN` 提升限流；不填也能跑（限流更低）。

> 测试默认走 hermetic 路径（`backend/conftest.py` 设 `USE_CHROMA=false`），**不下载嵌入模型**，秒级完成。

## 本机运行（前端）

需先装 Node.js 24 LTS 与 pnpm。

```bash
cd frontend
pnpm install
pnpm dev                # 起在 127.0.0.1:5173，/api 代理到后端 :8000
```

浏览器开 http://127.0.0.1:5173，输入 `https://github.com/psf/requests` 之类即可看路线图。

## LLM 配置

不配置 Key 也能跑：生成会走**确定性启发式**路径（`core/generate/pipeline.py` 的 `_generate_heuristic`），用于演示与 CI。要启用 AI 生成，二选一：

- 页面右上角「设置我的 LLM」填写（发送到本地后端并仅存**当前进程内存**，不写盘；只适合单用户本地演示）
- `backend/.env` 填 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`

任何 OpenAI 兼容端点均可，默认指向官方端点。使用第三方服务前请阅读 [docs/third_party_disclosure.md](docs/third_party_disclosure.md)。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/profile` | `{url}` → 仓库画像（languages / build / gfi / activity / suitability / reasons） |
| POST | `/api/search` | `{url, query, kind?}` → 按视角路由的检索结果（带证据来源） |
| POST | `/api/ask` | `{url, question, history?, revision?, use_llm?, model_timeout_s?}` → 中文解读、出处、命令入口、缺口与下一步；模型等待默认 40 秒，范围 10–120 秒 |
| POST | `/api/guide` | `{url, use_llm, model_timeout_s?}` → Stage A–D 结构化指南（每步带 `evidence`）；每阶段模型等待默认 25 秒，范围 10–120 秒 |
| POST | `/api/followup` | 三步追问：这步太粗 / 看不懂为什么 / 报错了 |
| GET/POST | `/api/llm-config` | 读取 / 设置当前后端进程的 LLM 配置（不回显 Key；仅限本地单用户演示） |
| GET | `/health` | 存活检查 |

完整约定见 [docs/code_outline.md](docs/code_outline.md)。

## 评测（四层，口径红线）

| 层 | 命令 | 说明 |
|---|---|---|
| L1 烟测 | `python -m benchmark.l1_smoke` | 离线、无 LLM、无 chroma，只验证链路通。**不产出质量数字** |
| L2 golden | `python -m benchmark.l2_golden.runner` | 对 golden 仓库跑真实生成，按五个指标评分 |
| L3 消融 | `python -m benchmark.l3_ablation.runner` | 同批仓库对比「朴素单次生成」vs「分层四视角管线」 |
| L4 真实贡献 | `python -m benchmark.l4_contribution.runner` | 用本产品实际提交 PR 的记录 |

新增真实模型受控实验：`python -m benchmark.controlled_ablation --repos pallets/click`，保存固定源码快照与原始模型输出；无密钥或模型失败时不会静默回退。旧实验分数与当前严格指标不可直接比较。

**口径红线（见 [benchmark/README.md](benchmark/README.md)）**：仓库内样例与烟测**不得**宣称生成质量；任何质量数字必须能回溯到人工复核过的 golden 仓库集。

指标定义在 `benchmark/metrics.py`：步骤完整率、证据命中率、命令正确率、命令可执行率、有据断言率。

## 许可证与第三方资源

本项目以 **MIT** 许可发布（见 [LICENSE](LICENSE)）。项目中使用的开源组件、开源模型、商业 LLM 服务及其许可条件，逐项列于 [docs/third_party_disclosure.md](docs/third_party_disclosure.md)。

本项目**不自称纯开源**：编排、分层索引、证据校验、评测体系为自主实现；通用大模型走商业 API。本地嵌入与向量检索使用开源组件，不依赖外部服务。

## 文档

- [当前验收与待办](docs/competition_readiness.md)：含追问原文核验、2026-10-21 报告更新及仍待人工完成的事项。

- [第四轮：固定参考与公平对照](docs/evidence_round4_20261018.md)：原文复核、对照协议修正和任务漏项修复。

- [第三轮连续流程优化](docs/workflow_round3_20261018.md)：克隆顺序、执行目录、输入路径、前置步骤和通用完成检查。

- [第二轮命令实跑](docs/execution_findings_20261018.md)：实际成功、失败、平台诊断及复现计划。

- [本轮真实模型发现与验收](docs/real_model_findings_20261018.md)：五仓库探索性实验、当前限制与下一步验收。
- 离线查看真实输出：前端点击“导入已保存指南”，选择 `output/guides/requests-20261018.json`。此模式不联网重验，不执行命令。

**面向评审**

- [docs/submission.md](docs/submission.md) — **作品说明**（选题论证 / 系统设计 / 验证证据 / 路线图）
- [output/pdf/OpenGuide-作品说明.pdf](output/pdf/OpenGuide-作品说明.pdf) — 作品说明 PDF 工作稿（由 Markdown 生成，待团队审核后定稿）
- [docs/demo_script.md](docs/demo_script.md) — 现场演示脚本（3 个真实仓库 + 兜底方案）
- [docs/video_script.md](docs/video_script.md) — 演示视频分镜脚本
- [docs/cold_start_checklist.md](docs/cold_start_checklist.md) — 2026-10-06 历史环境检查，不能替代当前版本的干净环境部署验收
- [docs/privacy_and_license.md](docs/privacy_and_license.md) — 隐私与授权说明
- [docs/evaluation_report.md](docs/evaluation_report.md) — **评测报告**（L2/L3 实测数字与归因）
- [benchmark/README.md](benchmark/README.md) — 评测方法论与口径红线

**开发与协作**

- [docs/task_book.md](docs/task_book.md) — 任务书（选题论证 / 技术方案 / 里程碑进度）
- [docs/team_roles.md](docs/team_roles.md) — 分工与进度快照
- [docs/code_outline.md](docs/code_outline.md) — 代码大纲与接口约定
- [docs/third_party_disclosure.md](docs/third_party_disclosure.md) — 第三方资源与许可披露
- [docs/changelog.md](docs/changelog.md) — 变更记录（含修复根因与验证口径）
