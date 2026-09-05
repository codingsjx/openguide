# OpenGuide 评测方法论（benchmark/）

评测分四层，口径红线：**仓库内样例/烟测不得宣称生成质量；任何质量数字必须能回溯到人工复核过的 golden 仓库集。**

## 分层

| 层 | 内容 | 目的 |
|---|---|---|
| **L1 烟测** `l1_smoke/` | 本地 fixture（不联网）喂固定步骤，只验证 URL→画像→(索引/生成 M1/M2 接入)→schema 链路通 | 跑 CI / 演示。**不代表生成质量** |
| **L2 黄金评估** `l2_golden/` | golden 仓库 + 人工"标准上手指南" + 规则化指标 | 量化生成质量；只报**已人工复核**数字 |
| **L3 消融** `l3_ablation/` | 同批仓库：朴素 baseline vs 分层管线 | 支撑"分层管线的价值"叙事；同批同基准防漂移 |
| **L4 真实贡献** `l4_contribution/` | 用本产品向小仓库走通真实 PR | 方向三闭环佐证（M5 填入链接） |

## 指标（benchmark/metrics.py，规则化、确定性）

- **step_coverage 步骤完整率**：生成的步骤覆盖了多少 golden 步骤
- **evidence_hit 证据命中率**：生成命令步骤里，证据 source 能否解析到真实仓库文件
- **command_exec 命令可执行率**：命令能否在真实 clone 上执行（需离线 runner，默认留待 runner 填）
- **assert_rate 有据断言率**：非 missing 证据占全部生成步骤比例（无证据不宣称 的直接度量）

## golden 仓库清单

见 `golden/repos.json`（2026-09-05 初选：psf/requests、camelot-dev/camelot、mochajs/mocha、pallets/click、cookiecutter/cookiecutter）。**build/test_cmd 待 C 人工复核定稿。**

## 人工标注流程（C 负责）

1. 对 `golden/repos.json` 每个仓库：clone 到本地，真实跑通 环境搭建 + 测试基线，把"能跑的命令 + 期望结果 + 出处文件"写成 golden guide JSON：
   `golden/golden_guides/<owner>__<repo>.json`（schema 见 `golden/schema.py`）。
2. 至少覆盖 A(环境搭建)+B(测试基线)；C(选 issue)/D(首PR) 视仓库而定。
3. 标注完把该仓库标记 `repos.json` 里 `verified: true`，评测才把它计入 L2 汇总。

## 如何运行

```bash
# 全部（L1-L4）
uv run python -m benchmark.runner

# 单层
uv run python -m benchmark.l1_smoke      # L1
uv run python -m benchmark.l2_golden     # L2
uv run python -m benchmark.l3_ablation   # L3
uv run python -m benchmark.l4_contribution # L4
```

输出：`reports/` 下 jsonl（逐条）+ summary json（汇总），为提交包证据。

## 待办

- [ ] C 人工复核 5 个 golden 仓库的 build/test_cmd
- [ ] C 撰写 `golden_guides/*.json`（先 requests，再 camelot/mocha）
- [ ] M1/M2 后：l2 接入真实生成器；l3 接 baseline+layered 生成器
- [ ] M5：l4 填真实 PR/commit
