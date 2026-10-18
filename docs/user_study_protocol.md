# 新手首次贡献用户实验方案

状态：方案已准备，尚未招募、执行或获得结果。不得将此文件写成用户效果佐证。

目标：比较阅读仓库官方文档与使用 OpenGuide 时，新手完成环境搭建、最小测试、选择真实任务的成功率和耗时。

1. 招募 8–12 位自愿参与的新手，记录语言经验和开源经验；只使用匿名编号。
2. 准备两个难度接近且已由组织者验证的仓库任务，固定 commit、操作系统、工具链和网络条件。
3. 随机将参与者分为 AB/BA 两组，分别先用文档或先用 OpenGuide；第二个任务交换条件，减少顺序影响。
4. 每个任务限时 30 分钟，预先写清成功标准：依赖安装成功、指定最小测试退出码为 0、选出当前开放且符合范围的 issue。
5. 记录总时间、各阶段成败、求助次数、错误命令次数、工具输出与人工修正。超时与退出必须保留，不能从分母剔除。
6. PR 提交另行自愿进行，不以批量提交低价值 PR 作为实验任务；维护者回复、接受和合并分开记录。
7. 报告样本数、成功人数/总人数、中位时间与分布；说明探索性小样本限制，不夸大因果和推广性。
8. 日志在参与者确认后脱敏，删除账号、密钥和非必要身份信息；原始数据不默认公开。

建议记录表：

```csv
participant_id,experience,sequence,task,condition,commit_sha,os,setup_ok,test_ok,issue_ok,elapsed_seconds,help_count,wrong_command_count,timed_out,notes
```

贡献案例另记：仓库、任务链接、使用的指南版本、工具帮助的具体步骤、人工修正、PR 链接、提交/关闭/合并状态和维护者反馈日期。

## 本地记录工具（尚无真人数据）

在仓库根目录运行，生成空白台账及描述性报告：

```powershell
python -m benchmark.user_study init --output _run_cache/user-study.json
python -m benchmark.user_study summarize _run_cache/user-study.json --output _run_cache/user-study-report.json
```

空台账状态为 `draft`，人数为 0，成功率为 null，不构成实验结果。工具不会覆盖已有文件；更新报告时使用新的文件名。

开始前填写 `tasks` 两项：`task_id`、`repo`、40 位 `commit_sha`、`environment`、`setup_success`、`test_success`、`issue_success`。组织者应在指定环境亲自验证任务后填写 `organizer_verified=true`，再把状态设为 `collecting`。此布尔字段是组织者声明，软件无法证明其真实性。开始后保留一份只读计划及哈希，不能根据结果修改成功标准。

实际招募后才填写 `participants`：匿名 `participant_id`（如 P001）、已取得同意的 `consent_recorded`、`experience`、`sequence`（AB/BA）、`first_task`。A 表示官方文档，B 表示 OpenGuide；第二个任务交换条件。不要用示例编号充当真实招募人数。

每次观察填写 `sessions`：`participant_id`、`task_id`、`condition`（official_docs/openguide）、`status`（completed/timed_out/withdrawn）、`elapsed_seconds`、`setup_ok`、`test_ok`、`issue_ok`、`help_count`、`wrong_command_count`、`observation_reference`，另可填 `notes`。OpenGuide 条件必须记录 `guide_revision`（代码版本及保存指南的定位信息）。观察引用应指向本地脱敏日志或组织者笔记，不要填密钥或个人姓名。退出必须记录原因，超过限时不能计为 completed。

报告以已招募且同意参加的人数作为每个条件的分母，保留缺失、退出和超时；同时列出实际观察人数及用时分布。用时中位数仅基于已有观察，不能隐去缺失情况，也不能直接推断工具带来因果收益。工具校验记录结构、分组和统计口径，无法独立核验观察真实性。原始台账默认放在被忽略的 `_run_cache`，不自动上传。
