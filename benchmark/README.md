# OpenGuide 评测方法与证据边界

正式效果结论应基于固定版本、适当范围和独立人工复核。AI 源码复核和规则校验可以用于探索性实验，但不能冒充人工金标准或新手成功率。

## 当前验证入口

| 入口 | 能证明什么 | 不能证明什么 |
|---|---|---|
| `python -m benchmark.l1_smoke` | 离线链路与结构约束 | 真实模型质量或用户效果 |
| `python -m benchmark.reference_audit` | 指定 SHA 的引用、行号与明示命令可找到 | 语义完整性、独立人工复核、执行成功 |
| `python -m benchmark.controlled_ablation` | 同快照、明确控制项下的模型输出与参考匹配差异 | 未测的命令执行或最终贡献结果 |
| `python -m benchmark.execute_reviewed` | 已审阅计划在记录环境中的执行结果 | 全平台成功率或任意生成命令安全性 |
| `python -m benchmark.l4_contribution.runner` | 已录入的贡献链接与状态 | 空记录不能证明真实贡献闭环 |
| `python -m benchmark.user_study` | 本地观察记录结构、分组与描述性统计 | 不能认证人工记录真实，空台账没有用户效果结论 |
| `python -m benchmark.readiness_audit` | 固定 Git 文档下的结构、引用与资料覆盖缺口 | 不执行命令，不测模型或新手成功率 |

旧 `golden_guides/`、L2/L3 与 2026-10-06 报告保留为历史记录；其中无 SHA 的旧标注和 fake 基线不用于新协议的正式结论。L4 无记录时为 PENDING，不能写成闭环完成。

## 新的固定参考集

`golden/pinned/` 保存 SHA、评分阶段、原文引句、行号、执行状态与人工复核状态。当前两份参考均为 `agent_source_reviewed`，独立人工复核 pending。
Requests 只评分 A/B；Click 只评分 B 的明示专项命令提取，不评价这些命令是否适合新手。未覆盖范围不得计作已验证。

```powershell
python -m benchmark.reference_audit --snapshots _run_cache/pinned_inputs --output benchmark/reports/pinned_reference_audit_20261018.json
python -m benchmark.controlled_ablation --reference-dir benchmark/golden/pinned --snapshot-dir _run_cache/pinned_inputs --repeats 2
```

上述快照目录是本机归档；外部复现须按固定提交准备相同输入并核对快照哈希。原始仓库文本、提示和响应不默认公开，统计与原始内容分开管理。

## 对照协议 2

- 普通 RAG 使用一个去重后的全局索引，不是四个独立索引结果的合并。
- 路由与全局检索均关闭 V3 专属命令加分；共享阶段提示、查询、候选排序、最终 top-k 和 token 上限。
- 两次重复交替生成顺序，保留失败和重试次数；不只挑表现最好的一轮。
- 后处理组复用同一份路由原始生成，包含证据审计、make 展开、流程排序和上下文推导。它检验组合后处理，不能分别归因各机制。
- 后处理记录增量耗时与包含生成的端到端耗时，不能把毫秒级审计耗时当作完整生成耗时。
- 单次全文生成组的输入、输出预算和调用次数不同，仅作产品基线，不作为路由机制的公平单变量对照。

## 指标解释

- `step_coverage`：一对一参考步骤匹配率，非真实用户任务成功率。
- `command_correct`：保留动作和参数的参考命令匹配率，非通用语义正确率；未收录的合理等价命令可能被拒绝。
- `command_coverage`：参考命令步骤覆盖，防止删除所有困难命令后匹配率虚高。
- `evidence_hit`：所有评分范围内步骤的来源路径命中率，非引文支持关系或事实正确率。
- `assert_rate`：非 missing 来源比例，非有据断言正确率。
- `command_exec`：只有明确执行才可赋值。受控生成实验没有运行命令，公开导出记为 null，不把内部默认 0 当成执行失败率。

当前两仓库、两次重复与不同范围，只能产生探索性结果，不支持统计显著性或普遍优越性的声明。人工复核清单见 `docs/reference_review_checklist.md`。
