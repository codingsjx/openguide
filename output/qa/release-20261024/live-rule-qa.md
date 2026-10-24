# OpenGuide 仓库问答记录

原文匹配不代表 AI 解读已独立复核，也不代表执行过命令。

## 问题 1：后端测试应该在哪个目录运行？

仓库：https://github.com/codingsjx/openguide
参考提交：22cd0e9d1148492498528c7f2502112ebd03806c
回答方式：原文整理

已找到可核对的测试入口：backend/README.md。 [S1]

原文操作的建议执行位置：backend。这是按原文上下文推导的位置，命令尚未执行。 [S1]

原文操作入口（未执行） [S1]：
```text
uv run pytest tests/ -q
```
执行位置（静态推导）：backend

下一步（通用建议）：
- 打开下方原文，核对完整前置条件及当前开发环境。
- 若仍不明确，补充操作系统、具体任务或脱敏异常，并继续追问。
- 记录实际退出码、失败与跳过数量，区分局部测试和完整测试。

出处：
- [S1 backend/README.md](https://github.com/codingsjx/openguide/blob/22cd0e9d1148492498528c7f2502112ebd03806c/backend/README.md#L1-L25)
- [S2 backend/README.md](https://github.com/codingsjx/openguide/blob/22cd0e9d1148492498528c7f2502112ebd03806c/backend/README.md#L20-L43)
- [S3 backend/pyproject.toml](https://github.com/codingsjx/openguide/blob/22cd0e9d1148492498528c7f2502112ebd03806c/backend/pyproject.toml#L1-L28)

采集及生成说明：
- 文件证据固定于提交 22cd0e9d1148492498528c7f2502112ebd03806c；issue 信息是独立采集的快照，操作前需核对最新状态。
- 本次使用原文整理，没有调用问答生成模型。
