# 评测报告

**运行日期**：2026-10-06
**运行命令**：`python -m benchmark.l2_golden.runner` / `python -m benchmark.l3_ablation.runner`
**原始数据**：`benchmark/reports/`（`l2_results.jsonl`、`summary_l2_*.json`、`l3_ablation_*.json`）

> **口径红线**（见 [`../benchmark/README.md`](../benchmark/README.md)）：
> 本报告的数字全部来自**人工复核过的 golden 仓库集**；L1 烟测不产出质量数字。
> L3 本次使用确定性替身臂（无 LLM Key），报告中标注为 fake，**不得当作模型质量引用**。

---

## 1. 运行配置

| 项 | 值 |
|---|---|
| 生成模式 | 无 LLM Key（确定性启发式路径）—— 与 CI / 离线评审一致，任何人可复现 |
| 向量检索 | `USE_CHROMA=false`（确定性词元检索，零模型下载） |
| 命令超时 | `OG_CMD_TIMEOUT=300`（单条命令上限，超时记为失败并标注原因） |
| 依赖准备 | 每个仓库独立 venv / `npm ci`，由评测框架自动完成（见 §4） |
| golden 仓库 | 5 个，全部 `verified: true` |

---

## 2. L2 黄金评估：总体结果

| 指标 | 数值 | 含义 |
|---|---|---|
| 步骤完整率 `step_coverage` | **53%** | 生成的步骤覆盖了 26 个 golden 步骤中的多少 |
| 证据命中率 `evidence_hit` | **75%** | 生成步骤的证据来源能否解析到真实仓库文件/issue |
| 命令正确率 `command_correct` | **67%** | 生成的命令与 golden 参考命令的语义一致率 |
| 命令可执行率 `command_exec` | **23%** | 命令在真实 clone + 已装依赖的环境里能否成功退出 |
| 有据断言率 `assert_rate` | **85%** | 非 `missing` 证据占全部生成步骤的比例 |
| 单仓库生成耗时 | 均值 **41.9s** | 含网络抓取与索引构建 |

样本量：5 个仓库 / 26 个 golden 步骤 / 20 个生成步骤。

### 2.1 逐仓库明细

| 仓库 | 步骤完整率 | 证据命中率 | 命令正确率 | 命令可执行率 | 有据断言率 | 耗时 |
|---|---|---|---|---|---|---|
| `psf/requests` | 60% | 75% | 67% | 50% | 75% | 171.7s |
| `mochajs/mocha` | 67% | 75% | 100% | 0% | 100% | 28.0s |
| `cookiecutter/cookiecutter` | 60% | 75% | 67% | 67% | 75% | 6.2s |
| `camelot-dev/camelot` | 60% | 75% | 100% | 0% | 100% | 1.8s |
| `pallets/click` | 20% | 75% | 0% | 0% | 75% | 1.6s |

---

## 3. 对低分项的归因（诚实分析）

低分不是"藏起来"，而是**评测体系真的在起作用**。逐项说明原因。

### 3.1 命令可执行率 23%：三类真实原因

框架会为每个仓库建独立环境并**真实安装依赖**（详见 §4），因此这里的失败是真实失败：

| 原因 | 案例 | 证据 |
|---|---|---|
| **聚合测试套件过重** | `mochajs/mocha` 的 `npm test` = `run-s lint test-node test-browser`，含 lint 与浏览器测试，超出 300s 上限 | `(超时 >300s)` 与 lint/knip 报错输出 |
| **命令依赖未声明的插件** | `pallets/click` 的 `tox r -e random` 需要 `uv-venv-lock-runner`（tox-uv 插件），contributing 文档未提 | `runner 'uv-venv-lock-runner' ... is not available (plugin may not be installed)` |
| **测试本身依赖外部网络** | `psf/requests` 的 `python -m pytest tests` 确实**运行了**，但有 2 个网络/TLS 相关用例失败 | pytest 输出尾部；golden guide 已记录"2 个失败为环境相关，非代码问题" |

**这三类都指向同一个有价值的产品结论**：指南给出的命令"语法正确"不等于"新手照着能跑通"。
这正是我们同时保留 `command_correct`（跑对没有）与 `command_exec`（跑得动吗）两个指标的
原因——单看任何一个都会失真。

> 后续改进方向：指南在给出聚合命令时，应同时给出**最小可用子集**
> （如 mocha 的 `npm run test-node`、click 的 `pytest tests/`），降低新手第一次尝试的门槛。

### 3.2 `pallets/click` 步骤完整率 20%：命令正确率与完整率的连带效应

click 的 golden guide 含 5 步，生成 4 步，但只有 1 步在标题/阶段匹配上对上。
根本原因是生成阶段把 contributing 文档里的 `tox r -e random` 当作测试命令，
而 golden 认为测试基线应是 `pytest`——命令选错会同时拉低
`step_coverage`（步骤匹配）与 `command_correct`（命令匹配）。

**这不是匹配算法的问题，而是命令选取质量问题**，已在 §3.1 的改进方向里覆盖。

### 3.3 有据断言率 85%：这是**设计使然**，不是缺陷

`assert_rate` 度量"非 missing 证据的占比"。分层管线在**无法验证**某步出处时，
会诚实地标 `missing`（宁可承认没找到），因此它的 `assert_rate` 天然低于
"什么都说有证据"的朴素方案。对照 L3 数据（§5）可以看清这一点：
朴素方案 `assert_rate` 100%，但其 `evidence_hit` 只有 10%——
**它声称的出处绝大多数是编的**。这正是「无证据不宣称」要防的情况。

---

## 4. 评测框架的环境准备（本轮修复）

要让 `command_exec` 有意义，必须先让命令**真的能跑**。本轮修复了三个使该指标失真的缺陷：

| 缺陷 | 后果 | 修复 |
|---|---|---|
| 只建虚拟环境、**不装依赖** | `tox` / `npm test` 一律"不是内部或外部命令"，指标实际在测"这台机器预装了什么" | 自动执行 `pip install -e .[dev]` / `npm ci`（可用 `OG_SKIP_PROVISION=1` 跳过） |
| Windows 上以裸名 `npm` 调用 subprocess | `CreateProcess` 不解析 `PATHEXT`，安装静默失败，且**失败仍写入"已准备"标记**导致永久跳过 | 用 `shutil.which` 解析出 `npm.cmd` 全路径；标记**仅在成功时**写入 |
| 内层 `pip()` 声明 `-> None` 且不返回 | 所有 `== 0` 判断恒为假，标记永不写入，每次重复安装 | 修正返回值 |

另：`git clone` 失败原先只报"clone 失败"，现改为抛出带 **git 原始 stderr** 的
`CloneError`（区分"未找到 git"/"超时"/"退出码非 0"），便于现场排查。

---

## 5. L3 消融：朴素单次生成 vs 分层四视角管线

**同一批仓库、同一份 golden、同一套指标**，只替换生成器。

| 指标 | naive 单次生成 | layered 分层管线 | 差值 |
|---|---|---|---|
| 步骤完整率 | 31% | **53%** | +22% |
| 证据命中率 | 10% | **85%** | **+75%** |
| 命令正确率 | 50% | **67%** | +17% |
| 有据断言率 | 100% | 85% | −15% |

### 5.1 怎么读这张表

- **证据命中率 +75% 是核心结论**：朴素方案把"模型声称的出处"照单全收，
  其中只有 10% 能解析到真实文件；分层管线经证据校验后达到 85%。
- **有据断言率的"下降"是诚实性的胜利**：朴素方案 100% 断言都有"证据"，
  但那些证据基本是编的。分层管线宁可把验证不过的标成 `missing`。
  **两个指标必须一起读**——只看 `assert_rate` 会得出完全相反的结论。
- **耗时**：本次两臂均用确定性替身（无 LLM Key），耗时≈0，**不能代表真实 LLM 成本**。
  真实模型的耗时对比需配置 Key 后用 `--provider auto` 重跑。

### 5.2 口径声明

本次 L3 的 `baseline_is_fake: true`（见 `l3_ablation_*.json`）。
替身臂的作用是**证明指标能检出「无据断言」**，而非提供模型质量对比数字。
真实模型对比需在配置 LLM Key 后重跑。

---

## 6. 尚未完成 / 已知限制

| 项 | 状态 | 说明 |
|---|---|---|
| L4 真实 PR 记录 | **PENDING** | 尚无真实提交记录；`l4_contribution` 明确标注待补充，不当作通过 |
| 真实 LLM 的 L2/L3 数字 | 未跑 | 需配置 Key；当前数字全部来自确定性路径（可复现性更好） |
| `pallets/click` 的命令选取 | 已知问题 | 见 §3.1、§3.2 |
| golden 集规模 | 5 个仓库 | 后续计划扩到 15–20 个，覆盖 Rust/Go/Java |

---

## 7. 复现方式

```bash
# 环境：Python 3.12 + Node 24（Node 仅 JS 仓库的 command_exec 需要）
pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings pytest

# L1 链路烟测（离线、不产出质量数字）
python -m benchmark.l1_smoke

# L2 黄金评估（联网；自动为每个仓库准备依赖）
python -m benchmark.l2_golden.runner
python -m benchmark.l2_golden.runner --repos psf/requests     # 单仓库

# L3 消融
python -m benchmark.l3_ablation.runner
python -m benchmark.l3_ablation.runner --provider auto        # 真实 LLM（需 Key）

# 环境变量
#   OG_CMD_TIMEOUT=300     单条命令超时（秒）
#   OG_SKIP_PROVISION=1    跳过依赖安装（快速跑批）
```

输出落在 `benchmark/reports/`：逐条 jsonl + 汇总 json。
