# OpenGuide · 开源项目新手贡献智能向导

[![CI](https://github.com/codingsjx/openguide/actions/workflows/ci.yml/badge.svg)](https://github.com/codingsjx/openguide/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

输入一个 GitHub 仓库 URL，OpenGuide 输出一份**带证据、可执行、会陪你走完每一步**的新手贡献路线图：环境怎么搭、测试怎么跑、第一个 issue 怎么选、首个 PR 怎么提。

> 核心边界：**无证据不宣称**。每条建议都要能回溯到仓库里的真实文件或 issue；不能确认的，宁可标 `missing` 并建议提问，也不编造安装命令或 issue 编号。

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

- 默认 `USE_CHROMA=false`：走**确定性检索**，零模型下载、秒级启动，适合离线评审。
  需要本地向量检索时在 `.env` 里设 `USE_CHROMA=true`（首次会下载嵌入模型）。
- 向量库与 GitHub 响应缓存挂在命名卷上，重启不丢、不重抓。
- 详细演示流程见 [docs/demo_script.md](docs/demo_script.md)。

---

## 本机运行（后端）

需先装 [uv](https://docs.astral.sh/uv/)（本项目用 uv 管理 Python 3.12）。

```bash
cd backend
uv sync                        # 按 uv.lock 安装依赖
uv run pytest tests/ -q        # 72 个单测
uv run uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

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

- 页面右上角「设置我的 LLM」填写（仅存**当前会话内存**，不写盘）
- `backend/.env` 填 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`

任何 OpenAI 兼容端点均可，默认指向官方端点。使用第三方服务前请阅读 [docs/third_party_disclosure.md](docs/third_party_disclosure.md)。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/profile` | `{url}` → 仓库画像（languages / build / gfi / activity / suitability / reasons） |
| POST | `/api/search` | `{url, query, kind?}` → 按视角路由的检索结果（带证据来源） |
| POST | `/api/guide` | `{url, use_llm}` → Stage A–D 结构化指南（每步带 `evidence`） |
| POST | `/api/followup` | 三步追问：这步太粗 / 看不懂为什么 / 报错了 |
| GET/POST | `/api/llm-config` | 读取 / 设置会话内 LLM 配置（不回显 Key） |
| GET | `/health` | 存活检查 |

完整约定见 [docs/code_outline.md](docs/code_outline.md)。

## 评测（四层，口径红线）

| 层 | 命令 | 说明 |
|---|---|---|
| L1 烟测 | `python -m benchmark.l1_smoke` | 离线、无 LLM、无 chroma，只验证链路通。**不产出质量数字** |
| L2 golden | `python -m benchmark.l2_golden.runner` | 对 golden 仓库跑真实生成，按五个指标评分 |
| L3 消融 | `python -m benchmark.l3_ablation.runner` | 同批仓库对比「朴素单次生成」vs「分层四视角管线」 |
| L4 真实贡献 | `python -m benchmark.l4_contribution.runner` | 用本产品实际提交 PR 的记录 |

**口径红线（见 [benchmark/README.md](benchmark/README.md)）**：仓库内样例与烟测**不得**宣称生成质量；任何质量数字必须能回溯到人工复核过的 golden 仓库集。

指标定义在 `benchmark/metrics.py`：步骤完整率、证据命中率、命令正确率、命令可执行率、有据断言率。

## 许可证与第三方资源

本项目以 **MIT** 许可发布（见 [LICENSE](LICENSE)）。项目中使用的开源组件、开源模型、商业 LLM 服务及其许可条件，逐项列于 [docs/third_party_disclosure.md](docs/third_party_disclosure.md)。

本项目**不自称纯开源**：编排、分层索引、证据校验、评测体系为自主实现；通用大模型走商业 API。本地嵌入与向量检索使用开源组件，不依赖外部服务。

## 文档

- [docs/task_book.md](docs/task_book.md) — 任务书（选题论证 / 技术方案 / 里程碑）
- [docs/team_roles.md](docs/team_roles.md) — 分工与每周清单
- [docs/code_outline.md](docs/code_outline.md) — 代码大纲与接口约定
- [docs/third_party_disclosure.md](docs/third_party_disclosure.md) — 第三方资源与许可披露
- [docs/demo_script.md](docs/demo_script.md) — 现场演示脚本（3 个真实仓库 + 兜底方案）
- [docs/changelog.md](docs/changelog.md) — 变更记录（合并修复与验证口径）
