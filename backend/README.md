# OpenGuide 后端（FastAPI）

仓库勘探 → 画像 → 四视角分层索引 → 结构化指南生成 + 证据校验 + 三步追问。

## 运行

需先装 [uv](https://docs.astral.sh/uv/)（本项目用 uv 管理 Python 3.12）。

```bash
cd backend
uv sync                        # 按 uv.lock 安装依赖
uv run pytest tests/ -q        # 62 个单测
uv run uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

可选：复制 `.env.example` 为 `.env`，填 `GITHUB_TOKEN` 提升 GitHub 限流；
填 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 启用 AI 生成。不填也能跑：
生成会走确定性启发式路径，测试与 CI 均在该路径下验证。

> 测试默认走 hermetic 路径（`conftest.py` 设 `USE_CHROMA=false`），
> 不下载嵌入模型，秒级完成。需要真实向量检索时设 `USE_CHROMA=true`。

## 目录

| 路径 | 说明 |
|---|---|
| `src/backend/api/` | HTTP 层：profile / search / guide / followup / settings 路由 |
| `src/backend/core/github/` | GitHub API 封装、限流缓存、仓库勘探（M0） |
| `src/backend/core/profile/` | 画像 schema 与构建 |
| `src/backend/core/index/` | 四视角分层索引与检索（M1） |
| `src/backend/core/decide/` | 适不适合新手的决策树（纯规则，可单测） |
| `src/backend/core/generate/` | Stage A–D 结构化生成 + 证据锚点校验（M2） |
| `src/backend/core/followup/` | 三步追问：这步太粗 / 看不懂为什么 / 报错了 |
| `tests/` | pytest（默认离线、无密钥） |

完整接口约定见 [../docs/code_outline.md](../docs/code_outline.md)。
