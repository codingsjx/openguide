# 第二轮：命令实跑与可执行指南

日期：2026-10-18。保持现有项目方向和申报分类；本轮没有新增模型抽样，复用上一轮原始模型输出进行确定性回放和真实执行验证。

## 实跑结果

环境为 Windows 11、Python 3.12.8。两个仓库分别使用专用 venv，固定源码提交；这是依赖隔离，不是操作系统安全沙箱。子进程不继承 API 密钥环境变量。验证计划由 AI 辅助审阅，仍需团队独立人工复核。

| 仓库与操作 | 实际结果 | 结论边界 |
|---|---|---|
| Requests 开发依赖安装 | 退出码 0 | 只证明记录环境安装成功 |
| Requests 原始完整 CI recipe | 625 passed、6 failed、3 skipped、1 xfailed | 整体失败，不可写成全量通过 |
| Requests 数据结构测试子集 | 24 passed | 审阅者另选的诊断子集，不代表完整 CI |
| Click 直接 pytest 基线 | 2179 passed、107 skipped、31000 deselected、1 xfailed | 使用仓库默认测试配置，stress 等未选中；不证明 tox random 可运行 |
| Requests 证书单例第一次链接还原尝试 | 1 failed、340 deselected | 保留失败；Windows 相对链接分隔符尚未正确处理 |
| Requests 证书单例再次复测 | 1 passed、340 deselected | 链接恢复后单例通过；没有据此推断完整 CI 全部通过 |

Requests 固定提交为 `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`，Click 为 `2247b35ea1c47c727d7a06e51fa280e12a863ff6`。
Requests 的其余失败涉及代理、网络和超时行为，尚未逐一验证原因或解决。代码审阅发现测试会主动清理代理环境变量，因此不能简单通过设置 `NO_PROXY` 推断它们将通过；本轮没有修改系统代理设置。

结构化、脱敏统计见 `benchmark/reports/execution_validation_20261018.json`。原始日志和依赖快照仅保存在本地 `benchmark/reports/execution_*/`，未纳入 Git 或分发包。

## 由结果驱动的产品修复

1. 支持将 `make ci` 等简单目标展开为原文中的单条命令。只处理无前置目标、单条 recipe、无变量与复合 shell 语法的目标；保留原建议、展开说明和原文行号。复杂 Makefile 明确不猜测。
2. 测试检索优先普通基线，降低 randomized、stress、coverage、browser 等专项命令挤占入口的机会。
3. 保存指南可附带命令执行记录；导入时校验记录的命令和 commit SHA，页面明确显示历史环境、通过/失败及适用边界。它不是加密签名或独立真实性证明。
4. GitHub 语言、目录、任务和活跃度抓取失败时，标记未取得并降低推荐确定性，不再将其当成负面事实。部分任务抓取成功时保留已取得内容。
5. 仓库符号链接进入画像信号；指南提示 Windows 克隆需核对链接，避免路径与证书测试失败。
6. 体检建议明确属于规则判断；由文件名猜测的测试工具标为候选，help wanted 不再直接描述为可认领的 good-first-issue。

## 复现

先将公开仓库克隆至 `_golden_work/psf__requests` 和 `_golden_work/pallets__click`，分别 checkout 到上述提交，再运行：

```powershell
python -m benchmark.execute_reviewed benchmark/execution_plans/requests_windows_py312.json
python -m benchmark.execute_reviewed benchmark/execution_plans/click_windows_py312.json
```

失败或超时返回非零退出码；setup 失败后的测试记录为 blocked_by_setup。每次保存命令 argv、退出码、日志、环境和依赖版本；超时终止该次进程树。Requests 的符号链接修复后单例计划是单独诊断，不默认修改检出目录。

## 仍需补齐

固定提交的人工标准答案复核、更多环境与仓库验证、真实新手用户实验、上游贡献结果、最终视频和答辩材料。当前证据不能证明达到国一，也不能将两仓库的执行结果推广为全平台成功率。

## 工程验收

本轮后端与评测测试 129 项通过，前端导入验证 7 项通过，lint、生产构建和 L1 链路烟测通过。浏览器已验收命令展开、历史失败记录和重新导入时的进度重置。手动标记完成不再被描述为实际贡献完成。
