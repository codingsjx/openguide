# OpenGuide 前端（React + TypeScript + Vite + Ant Design）

OpenGuide 的交互层：仓库体检卡 → 分步贡献指南向导 → 三步追问 → 证据面板。

## 运行

需先装 Node.js 24 LTS 与 pnpm。

```bash
cd frontend
pnpm install
pnpm dev                # 起在 127.0.0.1:5173，/api 代理到后端 :8000
```

浏览器打开 http://127.0.0.1:5173 ，输入 `https://github.com/psf/requests`
之类即可看到体检卡与路线图。开发时请先启动后端（见 `../backend/README.md`），
否则前端会提示后端未连接。

## 构建与检查

```bash
pnpm build              # tsc 类型检查 + 生产构建（产物在 dist/）
pnpm lint               # oxlint
pnpm preview            # 本地预览构建产物
```

生产部署时把 `dist/` 与后端放在同一源下即可，`/api` 无需额外配置；
若前后端分开部署，用 `VITE_API_BASE` 指向后端根地址。

## 目录

| 路径 | 说明 |
|---|---|
| `src/pages/HomePage.tsx` | 首页：地址输入 + 三个结果标签页 |
| `src/pages/GuidePage.tsx` | 贡献问答检索（带来源证据） |
| `src/components/ProfileCard/` | 仓库体检卡（语言构成 / 构建 / 建议） |
| `src/components/GuideGenerator/` | 生成贡献指南（AI / 本地规则两种模式） |
| `src/components/GuideWizard/` | 分步向导 + 三步追问 + 证据面板 |
| `src/api/client.ts` | 后端接口封装 |
| `src/types/` | 与后端 schema 对应的 TS 类型 |
