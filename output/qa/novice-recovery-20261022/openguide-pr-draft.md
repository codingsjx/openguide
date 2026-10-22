# PR 草稿：修复新手走查中的排错、任务选择和 PR 草稿断点

状态：待人工审阅，未提交。
由 OpenGuide 在本机按用户填写的任务、修改和测试记录整理；内容及来源未独立核验，不代表测试已执行、贡献已完成或维护者已接受。请按仓库政策披露实际 AI 协助范围。

## 任务来源
仓库：https://github.com/codingsjx/openguide
指南参考资料提交：8c21e6d43798c707b5aa5001112719e832ae95a8
用户记录的改动基准：5fb320ddacb64a929fc86b9b73bcc16cd9a592b0
改动基准与指南参考资料版本不同，请重新核对贡献规范及验证要求。

人工选题；尚未关联 issue，请先确认维护者是否接受。

## 问题与范围
来源：2026-10-22 本地 AI 模拟新手走查。证书路径报错曾被误判为依赖源超时；issue 阶段缺少候选链接；阅读贡献规范后没有整理实际改动及验证记录的入口。范围保持开源新手贡献向导，不是上游 Requests 的修改。

## 实际修改（用户提供）
本轮已新增只读诊断检查和异常分类；任务采集支持有界开放 issue 浏览样本、空结果解释、检索入口及已有方案提醒；贡献工作台将用户提供的实际改动、可选 diff 和测试状态整理为本机草稿。补充隔离环境说明、完整命令复制及仅查看步骤，合并重复空步骤。以下路径来自本轮本地 Git 变更清单；完整改动需审阅改进分支。

修改文件：
- README.md
- backend/src/backend/api/routes/followup.py
- backend/src/backend/core/followup/diagnostics.py
- backend/src/backend/core/followup/service.py
- backend/src/backend/core/generate/heuristic.py
- backend/src/backend/core/generate/issues.py
- backend/src/backend/core/generate/pipeline.py
- backend/src/backend/core/generate/schemas.py
- backend/src/backend/core/generate/workflow.py
- backend/src/backend/core/github/recon.py
- backend/tests/test_api_followup.py
- backend/tests/test_api_guide.py
- backend/tests/unit/test_collection_status.py
- backend/tests/unit/test_novice_recovery.py
- backend/tests/unit/test_revision_collection.py
- backend/tests/unit/test_stage_fallback.py
- backend/tests/unit/test_workflow_context.py
- frontend/package.json
- frontend/src/api/client.ts
- frontend/src/components/ContributionWorkbench/index.tsx
- frontend/src/components/GuideWizard/index.tsx
- frontend/src/types/contribution.ts
- frontend/src/types/guide.ts
- frontend/src/types/savedGuide.ts
- frontend/tools/test-contribution.mjs
- frontend/tools/test-saved-guide.mjs
路径依据：用户手工填写，未核对工作区。

## 验证记录
用户记录为通过（未经工具执行验证）

实际命令：python -m pytest backend/tests benchmark/tests -q
退出码：0
结果摘要：2026-10-22 本地最终运行：209 passed，14.21 秒，1 条依赖弃用警告，包含 GitHub 采集失败仍可本机排查的回归。补充验证：frontend 目录 npm test 为 19 passed；npm run lint 与 npm run build 退出 0；L1 离线链路烟测通过。以上验证的是 OpenGuide 本轮修改；Requests 全套测试没有重新运行，真人试用及独立人工复核仍未完成。

## 仓库规范入口
未取得贡献规范，请先查看仓库最新说明。

## 提交前检查
- [ ] 确认任务仍需处理、没有重复 PR，且符合维护者参与规则
- [ ] 核对分支、实际 diff 与本草稿内容一致
- [ ] 处理失败或未运行项，按仓库要求记录验证范围和限制
- [ ] 补充仓库 PR 模板所需内容及实际 AI 协助披露
- [ ] 人工审阅后再决定是否向上游提交
