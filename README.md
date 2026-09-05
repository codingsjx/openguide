# OpenGuide · 开源项目新手贡献智能向导

M0 骨架：输入 GitHub 仓库 URL → 后端抓取并输出「画像 JSON + AI 体检建议」→ 前端渲染体检卡。

## 代码结构

| 目录 | 内容 | 主责 |
|---|---|---|
| `backend/` | FastAPI：仓库勘探 / 画像 schema / GitHub client / 决策树 | A |
| `frontend/` | React + Vite + antd：URL 输入页 + ProfileCard 体检卡 | B |
| `docs/` | 任务书 / 分工 / 代码大纲 | 全组 |
| `.claude/launch.json` | 本机 dev server 启动配置 | — |

## 本机运行（后端）

需先装 [uv](https://docs.astral.sh/uv/)（本项目用 uv 管理 Python 3.12）。

```bash
cd backend
uv sync          # 安装依赖（含 pytest）
uv run pytest tests/ -q        # 17 个单测应通过
uv run uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

可选：`backend/.env`（复制 `.env.example`）填 `GITHUB_TOKEN` 提升限流；不填也能跑（限流更低）。

## 本机运行（前端）

需先装 Node.js 24 LTS（本机解压在 `C:\Users\sjx11\node\node-v24.20.0-win-x64`，已写入用户 PATH）。前端依赖用 pnpm。

```bash
cd frontend
corepack enable pnpm    # 一次性
pnpm install
pnpm dev                # 起在 127.0.0.1:5173，/api 代理到后端 :8000
```

浏览器开 http://127.0.0.1:5173，输入 `https://github.com/psf/requests` 之类即可看体检卡。

## API（当前已实现）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/profile` | `{url}` → `Profile`（含 languages/build/gfi/activity/suitability/reasons） |
| GET | `/health` | 存活检查 |

完整接口约定见 [docs/code_outline.md](docs/code_outline.md) §2/§5。

## 下一步（M1）

四视角分层索引 + 检索打通（chromadb + sentence-transformers）。分工与每周清单见 [docs/team_roles.md](docs/team_roles.md)。
