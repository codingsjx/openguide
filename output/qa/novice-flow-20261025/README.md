# 新手贡献流程验收（2026-10-25）

研究与范围见 [本轮说明](../../../docs/novice_flow_research_20261025.md)。

- `paired-question.json`：同一真实仓库快照/问题的旧新代码对照；没有外部模型调用。
- `question-after.json`、`http-question-after.json`：本轮原文操作与固定版本行号。
- `live-ai-question-after.json`、`live-ai-question-summary.json`：一次真实模型调用失败，原文操作仍保留；不计为 AI 解读成功。
- `browser-checks.json`：同版本重新生成、不同仓库隔离、返回恢复和请求失败后的表单/草稿保留。
- `agent-preparation-before.json`、`agent-preparation-after.json`、`agent-preparation-final.json`：由页面主动导出的实际准备记录，用于逐字段比较；不是向页面注入结果。
- `agent-pr-draft.md`：代理在本项目完成实际后端修复后，由页面整理的本机草稿。包含修改前情况、验收计划、3 个实际变更文件及 340 项后端测试结果；尚未提交 PR，不是上游采纳或真人效果。

原始输入、开发日志和完整工作副本留在忽略目录；认证配置没有写入这些文件。阅读核对、基线记录、本次改动后的测试、草稿整理和上游接受分别说明。
