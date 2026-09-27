# 第三方资源与开源许可披露

本文件按 2026AIC·「AI+开源」算法主题赛对「开源及第三方资源披露、知识产权与许可合规」的要求，如实说明 OpenGuide 使用的第三方资源及其许可条件。

> 口径：本项目**不自称纯开源**。编排、分层索引、证据校验、评测体系为团队自主实现；通用大模型走商业 API 调用。下表按「自主实现 / 开源依赖 / 商业服务」三类分开说明，避免把外部能力记作自研成果。

## 1. 团队自主实现的部分

以下为本仓库原创代码（MIT，见 `LICENSE`）：

| 模块 | 位置 | 说明 |
|---|---|---|
| 仓库勘探与画像 | `backend/src/backend/core/github/` | 只抓「决策相关」信号（语言占比、构建面、gfi、活跃度、协议），输出固定 schema |
| 四视角分层索引 | `backend/src/backend/core/index/` | 按新手阅读路径把仓库重组为 V1 入口约定 / V2 架构地图 / V3 可执行路径 / V4 issue 槽位，各视角独立建索引 |
| 决策树 | `backend/src/backend/core/decide/` | 纯规则判定「适不适合新手」，模型无关、可单测 |
| 结构化指南生成 | `backend/src/backend/core/generate/` | Stage A–D 分阶段生成 + Pydantic schema 约束 + 证据锚点校验（无证据不宣称） |
| 证据审计 | `backend/src/backend/core/generate/evidence.py` | 每条断言的 `source` 必须回溯到真实抓取到的文件 / issue，否则降级为 `missing` |
| 分步引导交互 | `frontend/src/components/GuideWizard/` | 向导卡片流 + 三步追问 + 证据面板 |
| 分层评测体系 | `benchmark/` | L1 烟测 / L2 golden / L3 消融 / L4 真实贡献 |

## 2. 开源依赖（代码库）

各组件按其自身许可使用，**其许可不因本项目而改变**。版本以 `backend/pyproject.toml`、`frontend/package.json` 及对应锁定文件为准。

### 后端（Python）

| 组件 | 版本约束 | 许可 | 用途 |
|---|---|---|---|
| FastAPI | `>=0.115` | MIT | HTTP API 框架 |
| Uvicorn | `>=0.52.4` | BSD-3-Clause | ASGI 服务器 |
| Pydantic | `>=2.7` | MIT | 数据结构校验 |
| pydantic-settings | `>=2.3` | MIT | 配置加载 |
| HTTPX | `>=0.27` | BSD-3-Clause | GitHub API / LLM 调用 |
| ChromaDB | `>=1.5.9` | Apache-2.0 | 本地向量存储 |
| sentence-transformers | `>=6.0.1` | Apache-2.0 | 本地嵌入模型加载 |
| pytest | `>=9.1.1`（dev） | MIT | 测试框架 |

### 前端（TypeScript）

| 组件 | 版本约束 | 许可 | 用途 |
|---|---|---|---|
| React / React DOM | `^19.2.8` | MIT | UI 框架 |
| Ant Design (antd) | `^6.6.2` | MIT | 组件库 |
| @ant-design/icons | `^6.3.4` | MIT | 图标 |
| Vite | `^8.2.2` | MIT | 构建工具 |
| TypeScript | `~6.0.2` | Apache-2.0 | 类型系统 |
| Oxlint | `^1.79.0` | MIT | Lint |

## 3. 开源模型与数据

| 名称 | 许可 | 用途与边界 |
|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | Apache-2.0 | 本地嵌入模型，用于视角检索 |
| ONNX `all-MiniLM-L6-v2`（ChromaDB 内置嵌入函数） | Apache-2.0 | ChromaDB 默认嵌入，首次使用时自动下载 |

**说明**：嵌入与检索完全在本地完成，不依赖任何外部服务。若模型不可用，`USE_CHROMA=false` 会回退到确定性的本地 token 重叠检索（`backend/src/backend/core/index/vectorstore.py`），使测试与演示在离线环境下仍可运行。

## 4. 商业 LLM 服务

| 项 | 说明 |
|---|---|
| 用途 | Stage A–D 指南文本生成、三步追问的解释 |
| 接口形态 | OpenAI 兼容的 Chat Completions / Responses 接口 |
| 默认端点 | `https://api.openai.com/v1`（见 `backend/src/backend/config.py`、`backend/.env.example`） |
| 可替换性 | 任意 OpenAI 兼容端点均可，通过 `.env` 的 `LLM_BASE_URL` 或前端「设置我的 LLM」配置 |
| 密钥处理 | 仅存本地 `.env` 或**当前会话内存**（`backend/src/backend/core/generate/llm.py` 的进程内覆盖），不写盘、不入库、不记录日志、不进版本库 |

**关于第三方中转服务**：用户可以自行配置第三方中转端点。此类服务由用户自选并自行承担其服务条款与合规责任；本项目不内置、不推荐、不背书任何特定中转服务商，也不分发其凭据。仓库内的默认端点与文档示例均指向官方公开端点。

**与赛题红线的关系**：本赛题明确「仅调用通用模型接口……**且未形成实质改进的**，不视为充分完成作品」。本项目的实质改进在模型之外：

1. **四视角分层索引**——按新手阅读路径重组仓库，使「如何搭环境」这类跨文件问题可被单次检索命中，而非把全文塞进上下文；
2. **证据锚点与「无证据不宣称」**——生成后逐条校验证据可回溯性，不可回溯的断言降级为 `missing`，而非放任模型自由发挥；
3. **画像驱动决策树**——先判定仓库适不适合新手，不适合则输出理由而非硬生成指南；
4. **L1–L4 分层评测体系**——含 golden 人工标注、消融实验与真实贡献闭环，用于量化并公开上述机制的效果。

## 5. 参考与致谢

| 来源 | 许可 | 使用方式 |
|---|---|---|
| [RoomSense AI](https://github.com/yuval-haim/roomsense-ai) | MIT | **仅参考架构与测试方法**；本仓库实现为独立编写，未复制其源码，故未引入其许可文件 |

`benchmark/golden/` 下引用的 `psf/requests`、`pallets/click`、`cookiecutter/cookiecutter`、`mochajs/mocha` 等仓库：**仅作为评测对象被分析**，其源码不在本仓库内分发，各自许可见对应上游仓库。

## 6. 合规自查

- [x] 仓库含 `LICENSE`（MIT），与申报方向三「开源生态贡献」一致
- [x] 无密钥入库；`.env` 已在 `.gitignore`
- [x] 第三方组件按依赖清单逐个标注许可
- [x] 本地嵌入/检索使用开源组件，LLM 依赖如实披露为商业 API
- [x] 未分发任何受第三方许可限制的源码，仅引用并对上游做链接
- [ ] 提交前复核：依赖版本与许可以上游锁定文件为准（依赖升级后需同步本表）
