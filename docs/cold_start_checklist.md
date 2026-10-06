# 提交包冷启动演练记录

**目的**：任务书 §6.2 提醒"`.env.example` 与文档里启动路径不一致会导致评审无法复现"，
要求提交前做一次"从干净目录按文档冷启动"的演练。本文件记录演练过程与实测结果。

**演练日期**：2026-10-06
**演练环境**：Windows（PowerShell 7）、Python 3.12.8、Node 24.19、pnpm 12.5.1
**演练方式**：按根 `README.md` 与 `docs/submission.md` §7 的文档步骤逐条执行，不跳步、不预设环境

---

## 演练结果

| # | 步骤 | 文档出处 | 命令 | 结果 |
|---|---|---|---|---|
| 1 | 后端依赖锁一致性 | README §本机运行 | `uv lock --check` | ✅ 通过（Resolved 122 packages） |
| 2 | 后端测试 | README §本机运行 | `pytest backend/tests -q` | ✅ **68 passed** |
| 3 | 评测体系测试 | `benchmark/README.md` | `pytest benchmark/tests -q` | ✅ **14 passed** |
| 4 | L1 链路烟测 | README §评测 | `python -m benchmark.l1_smoke` | ✅ 通过（明确不产出质量数字） |
| 5 | 后端启动与存活检查 | README §本机运行 | `uvicorn backend.api.main:app` → `GET /health` | ✅ `200 {"status":"ok"}` |
| 6 | Docker Compose 配置校验 | README §一键部署 | 解析 `docker-compose.yml` | ✅ 两个服务（backend/frontend）+ 两个命名卷 + healthcheck 语法正确 |
| 7 | 前端依赖锁与生产构建 | README §本机运行 | `pnpm install --frozen-lockfile` + `pnpm build` | ✅ 构建成功（tsc 类型检查 + vite 打包） |

**7 / 7 全部通过。**

---

## 路径一致性核对

任务书点名的"打包硬伤"是**文档里的路径与实际文件不一致**。逐项核对：

| 文档中提到的路径 | 是否存在 |
|---|---|
| `docker-compose.yml` | ✅ |
| `.env.example`（顶层） | ✅ |
| `backend/.env.example` | ✅ |
| `backend/Dockerfile` | ✅ |
| `frontend/Dockerfile` | ✅ |
| `frontend/nginx.conf` | ✅ |
| `docs/demo_script.md` | ✅ |
| `docs/submission.md` | ✅ |
| `docs/video_script.md` | ✅ |
| `docs/privacy_and_license.md` | ✅ |
| `docs/third_party_disclosure.md` | ✅ |
| `docs/changelog.md` | ✅ |
| `docs/code_outline.md` | ✅ |
| `benchmark/README.md` | ✅ |
| `LICENSE` | ✅ |
| `.github/workflows/ci.yml` | ✅ |

**无悬空引用。**

---

## 启动方式与文档的一致性

`docker-compose.yml` 的端口与文档承诺一致，评审按文档访问即可：

| 服务 | 容器内 | 宿主机 | 文档中的地址 |
|---|---|---|---|
| frontend | 80 | 5173 | http://127.0.0.1:5173 |
| backend | 8000 | 8000 | http://127.0.0.1:8000 |

`.env.example` 的变量名与 compose 引用的变量名逐一对应（`GITHUB_TOKEN` / `LLM_API_KEY` /
`LLM_BASE_URL` / `LLM_MODEL` / `USE_CHROMA` / `VECTORSTORE_DIR`），无拼写漂移。

---

## 演练中发现并已修复的问题

本次演练与同步进行的代码体检共修复以下问题（详见 [`changelog.md`](changelog.md)）：

| 问题 | 影响 |
|---|---|
| GitHub 缓存在 Windows 上完全失效（缓存文件名含非法字符 `?`，异常被静默吞掉） | 每次运行都重打 API、很快耗尽限流，演示无法稳定复现 |
| V3「可执行路径」视角被无命令的叙述文档淹没 | "怎么跑测试"答不出来（含 `pytest` 的 Makefile 被挤出检索结果） |
| 构建文件（Makefile / pyproject.toml / package.json）从未被抓取 | 部分仓库的安装/测试命令无从获取 |
| 无 LLM 时 A/B/D 三阶段输出同一条安装命令 | 默认演示路径下路线图自相矛盾 |
| 证据来源与命令不对应、且丢失文件名大小写 | 违反「无证据不宣称」；前端"打开原始出处"链接 404 |
| L4 空记录被当作失败 | 全量评测误报"未通过" |

---

## 未能覆盖的部分（需团队在演示机复核）

| 项 | 原因 | 建议 |
|---|---|---|
| `docker compose up --build` 实际构建 | 演练环境未安装 Docker | 提交前在装有 Docker 的机器上跑一次完整构建 |
| 真实 GitHub API 全链路（L2/L3 全量跑批） | 演练环境 IP 触发匿名限流（60 次/小时） | 在演示机配置只读 `GITHUB_TOKEN` 后跑全量，结果落 `benchmark/reports/` |
| 演示视频录制 | 需人工操作 | 按 [`video_script.md`](video_script.md) 录制 |

---

## 复现命令（供评审核对）

```bash
# 1. 后端
cd backend
uv sync
uv run pytest tests/ -q          # 68 passed
cd ..
python -m benchmark.l1_smoke     # L1 通过

# 2. 前端
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ..

# 3. 一键部署（需 Docker）
cp .env.example .env
docker compose up --build
# 浏览器打开 http://127.0.0.1:5173
```
