# 逐步 AI 讲解验收

详见 [修复说明](../../../docs/ai_step_tutoring_20261025.md)。

- `baseline.json`：同一仓库版本的原文规则流程。
- `summary.json` / `guide-live.json`：首次大批次失败，0/11；保留以说明截断问题。
- `fixed-batch-*.json`：早期六步批次实跑，10/11。
- `refined-batch-*.json`：中间校验实跑，9/11。
- `final-batch-*.json`：最终代码、已采集固定输入的真实模型生成，11/11。
- `browser-first.json`：第一次页面验收，10/11。
- `browser-final.json` / `browser-final-summary.json`：最终网页实际生成并导出的 11/11 结果，不是向页面注入或回放输出。
- `full-coverage.png`：最终页面截图。手动进度不代表执行验证，不计入任务成功。
- `ask-live.json`：模型因资料不足未给出要点，未计作 AI 回答成功。

命令、目录、引用、前置关系和执行状态均保持规则基线的值。AI 讲解不等于语义独立复核或命令执行。记录属于开发过程中的不同代码版本，不合并计算稳定性成功率。原始提示和响应仅留在忽略目录 `_run_cache/step-tutoring-20261025/`，配置与密钥不进入公开材料。
