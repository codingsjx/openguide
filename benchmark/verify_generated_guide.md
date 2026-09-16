# 评测脚本 verify_generated_guide.py 使用说明

> 本文档说明 `benchmark/verify_generated_guide.py` 的功能、运行逻辑与使用方法。

## 一、这个脚本是干什么的

它**评测 OpenGuide 生成器真正产出的 guide 的质量**——不是我们手写的 golden，而是后端 `/api/guide` 生成给新手的那份指南。

脚本会调后端生成器，拿到生成的 guide，然后在**真实环境**里执行 guide 里的命令，并输出五个维度的质量分数：

| 维度 | 含义 | 回答的问题 |
|---|---|---|
| **步骤完整率** `step_coverage` | 生成的步骤覆盖了 golden 标准答案多少步 | 该给新手的步骤给全了吗 |
| **证据命中率** `evidence_hit` | 命令的证据出处能否回溯到真实文件 | 引用来源是真的吗 |
| **命令正确率** `command_correct` | 命令与 golden 标准命令对不对得上 | 命令跑对了吗（而非只是跑得动） |
| **命令可执行率** `command_exec` | 命令在真实环境里能否跑通（退出码 0） | 新手照着敲会不会卡住 |
| **有据断言率** `assert_rate` | 非 missing 证据的步骤占比 | 有多少步骤敢标出处 |

**核心价值**：前三个率都需要 golden 当"标准答案"来参照；而命令可执行率由脚本实测、任何仓库都能算。五个数字合起来，才是生成器质量的真实画像（比如"命令能跑但命令错了"这种问题，单看可执行率 100% 会被掩盖，命令正确率能把它揪出来）。

## 二、使用方法

```bash
# 测指定仓库（owner/repo 或完整 URL 均可）
backend/.venv/Scripts/python.exe benchmark/verify_generated_guide.py psf/requests pallets/click

# 不传参数 = 测默认 4 个仓库
backend/.venv/Scripts/python.exe benchmark/verify_generated_guide.py

# 清空缓存（磁盘紧张时用）
backend/.venv/Scripts/python.exe benchmark/verify_generated_guide.py --cleanup
```

**注意**：脚本内部走 `use_llm=False` 的离线启发式生成，**不需要 LLM Key**。但 clone 仓库、装依赖需要联网（走 git 代理，见环境说明）。

## 三、运行逻辑（8 个机制）

对每个仓库，脚本按顺序执行：

1. **解析参数**：支持 `owner/repo` 或完整 URL；不传则用默认 4 仓库。
2. **生成 guide**：调后端生成器 `make_guide(...)`，`use_llm=False` 离线生成。
3. **缓存**：判断 `_run_cache/<owner>__<repo>/repo/` 有无 `.git`，有则复用（跳过 clone），无则 `git clone --depth 1`。
4. **识别语言**：看根目录文件——有 `package.json` → JavaScript；有 `pyproject.toml`/`setup.py`/`requirements.txt` → Python。
5. **建环境**：Python 仓库在缓存目录建 venv，返回 `venv/Scripts` 作为 PATH 前缀；Node 仓库用系统 Node 安装目录。
6. **跑命令**：把 PATH 前缀注入环境变量后执行每条命令；900 秒超时保护；UTF-8 容错读取输出。
7. **五维度评分**：命令可执行率由脚本实测；其余四维度在"该仓库有 golden 参照"时调 `benchmark.metrics.compute()` 计算。
8. **输出报告**：终端实时打印 + 按仓库汇总 + 总汇总 + JSON 报告落盘。

## 四、关键机制详解

### 4.1 缓存机制（省磁盘/省时间）

- 每个仓库 clone 到 `_run_cache/<owner>__<repo>/repo/`，用 `<owner>__<repo>` 命名（`/` 不能出现在目录名里，故用 `__` 替代）。
- 跑前判断 `.git` 是否存在：有 → 复用；无 → 重新 clone。
- `--cleanup` 直接 `rm -rf` 整个 `_run_cache/`。

### 4.2 识别环境机制（命令在不同语言环境跑）

- `detect_lang` 看根目录文件自动判语言，**不需要人填 env/lang 字段**（这是相对旧版 verify_commands.py 的关键改进）。
- `provision_env` 按语言返回"额外 PATH 前缀"：Python 用 venv 的 `Scripts`，Node 用系统 Node 目录。跑命令时这个前缀被加到 `PATH` 最前面，让 `python`/`pip`/`pytest`/`npm` 解析到正确版本。

### 4.3 处理 git clone / cd 的机制（环境初始化命令）

- 生成器给新手的 guide 第一步往往是 `git clone`。但脚本为了测命令，**自己已经先 clone 过了**；如果再照着 guide 里的 `git clone` 真跑，会因"目录已存在"而失败。
- 所以脚本把 `git clone`、`cd` 这类"环境初始化命令"标记为**「代劳」**，不重复实测，也不计入命令可执行率分母。
- 它们的正确性由"命令正确率"维度判断（跟 golden 标准命令比对），而非"可执行率"。

### 4.4 命令执行的容错

- **超时保护**：每条命令 900 秒超时，防止卡死拖垮整个脚本。
- **编码容错**：用 `encoding="utf-8", errors="replace"` 读输出，避免 Windows 下中文/emoji 输出把脚本搞崩。

### 4.5 五维度评分的"两条线"

脚本的评分分两条独立路径：

- **线 1（命令可执行率）**：脚本自己在环境里跑命令、数退出码为 0 的比例，**不依赖 golden**，任何仓库都能算。
- **线 2（其余四维度）**：先 `find_golden` 找该仓库有无 golden guide——有则把生成结果转成 benchmark 标准格式、调 `compute()` 算；无则跳过，只报命令可执行率并打印"（无 golden 参照）"。

这让脚本既能当"golden 评测"用，又能当"任意仓库的命令验证器"用。

## 五、输出说明

脚本输出分三层：

1. **终端实时打印**：每个仓库的五个率 + 失败命令明细（含具体错误输出）。
2. **汇总行**：所有仓库的总命令数、成功数、总可执行率。
3. **JSON 报告**：写到 `benchmark/reports/guide_quality_<时间戳>.json`，含每个仓库的五个维度 + 失败命令完整错误信息，可存档、可复现。

## 六、实测结果示例（requests）

```
[代劳] 本地搭建并跑起来: git clone ...  (环境初始化命令，脚本已代执行，不实测)
步骤完整率 60% | 证据命中率 67% | 命令正确率 67% | 命令可执行率 100% | 有据断言率 75%
总计 2 条命令 | 成功 2 | 命令可执行率 100%
```

这真实暴露了生成器当前的问题：命令能跑（可执行率 100%），但命令不对（正确率 67%）、证据不全（命中率 67%）。

## 七、环境依赖

- Python：`backend/.venv`（用 `uv run --python 3.13` 建的 venv）。
- Node：`C:\Users\Lenovo\node\node-v24.21.0-win-x64`（脚本里硬编码的 `NODE_DIR`，换机器要改）。
- 网络：clone 仓库、装依赖需要联网，git 需配代理（代理地址 `127.0.0.1:7897`，网络不通时手动切换直连/代理）。

## 八、相关文件

| 文件 | 作用 |
|---|---|
| `benchmark/verify_generated_guide.py` | 本脚本（评测生成 guide） |
| `benchmark/metrics.py` | 五维度的计算逻辑（`compute()`） |
| `benchmark/golden/schema.py` | golden 标准答案的格式定义 |
| `benchmark/golden/golden_guides/*.json` | 各仓库的 golden 标准答案 |
| `benchmark/verify_commands.py` | 旧版（测 golden 命令，已被本脚本取代） |
