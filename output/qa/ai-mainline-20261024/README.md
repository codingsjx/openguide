# AI 主线验收记录（2026-10-24 晚间）

完整解释见 [本轮报告](../../../docs/ai_mainline_20261024.md)。所有记录均为代理验收，不是真人试用；独立人工复核仍待完成。

| 文件 | 范围 |
|---|---|
| summary.json | 版本、测试结果、各批次统计及限制 |
| repeated-generations.json | 核心 34907cf，两个仓库各三次普通响应真实生成，含失败阶段 |
| ordering-replay.json | 当前顺序修复对上述六份真实输出的回放，新增模型请求为 0 |
| streamed-generations.json / stream-transport-probe.json | 可选流式实验；当前默认仍为非流式，不与普通批次合并 |
| same-repository-ai-guide.json / same-repository-help.json / same-repository-result.json | 核心 203707d：先真实生成指南，再在同版本独立副本构造缺 pytest 卡点，经原文入口恢复，固定子集 8 项通过 |
| blocker-help.json / blocker-result.json | 较早独立缺包验收，与上述连续实跑分别记录 |
| initial-exploration-limits.json | itsdangerous 初探的未完成项 |
| browser-before-order.json / browser-after-order.json | 页面实际生成结果，分别在顺序修复前后，不计入预先计划的六次统计 |
| ai-software-live-before-order.json / ai-software-guide-replayed.json | 较早真实输出及其离线回放示例，不能将回放称为新的模型结果 |
| ai-test-step.png / ai-test-step.txt | 当前页面 AI 测试步骤截图与范围说明 |
| ci-code.json | 核心 203707d 的五项 CI 成功记录 |

原始提示、完整响应和运行日志仅保留在被 Git 忽略的本地目录。公开文件不包含认证配置。测试命令的实际执行范围以 result 文件为准；指南中的“已核验”指来源核验，不代表命令执行成功。
