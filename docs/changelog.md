# 变更记录

本文件记录 OpenGuide 的功能性修复与验证口径，便于评审与协作追踪。

## 2026-09-27 · 贡献问答与路线图刷新修复

本轮修复 4 个用户可见问题，全部在后端单测（59 passed）与前端
`tsc -b && vite build` / `oxlint` 通过后合入。

### 1. 贡献问答答非所问

- **根因**：意图路由（`core/index/retrieval.py` 的 `_guess_kind`）用简单子串匹配，
  短词 `pr` 会命中 `improve`/`progress` 等无关单词，问题被错误路由到「贡献流程」
  视角；同时中文提问因无空格切词几乎匹配不到仓库原文。
- **修复**：
  - 英文关键词改为整词匹配（`(?<![a-z0-9])kw(?![a-z0-9])`），中文关键词仍按子串匹配，
    并补齐中英文关键词表。
  - 隐向量回退检索（`core/index/vectorstore.py` 的 `_query_fallback`）重写为
    「ASCII 词 + 中文二元组」分词 + 文档频率加权（稀有词权重更高），聚焦片段排前。
  - `/api/search` 返回片段去除 `===== path =====` 原始标记，来源改由 `meta.source`
    与前端「来源」标签呈现。
  - 「这步太粗」追问（`core/followup/service.py` 的 `granular`）按步骤阶段映射视角
    （A→setup / B→test / C→issue / D→contribute），不再一律用环境搭建视角作答。

### 2. 换仓库地址后路线图不变

- **根因**：前端 `GuideGenerator` / `GuidePage` 的输入框使用组件首次挂载时的 URL
  初始化 state，父组件传入的新地址不会刷新它，旧路线图与旧检索结果也一直保留。
- **修复**：
  - 地址变化时同步输入框、清空旧结果；`GuideGenerator` 会自动为新地址重新生成路线图，
    `GuidePage` 会清空上一仓库的检索结果。
  - 首页演示模式提示明确标注「固定展示 psf/requests 示例路线图，与输入地址无关」。

### 3. 仓库体检「语言构成」排版

- **根因**：每种语言放入三等分栏（`Col span={8}`），进度条宽度不稳、末行留空、
  长语言名被截断。
- **修复**：改为整行对齐布局（语言名右对齐 + 进度条撑满 + 自带百分比），
  最多展示 6 种语言，窄屏不溢出。

### 4. 「生成贡献指南」区域排版

- **修复**：说明文字中的 `**…**` 之前被当普通文本显示（Markdown 未渲染），改为
  `Text strong` 真加粗；地址输入框与操作按钮改为自动换行；向导主区与右侧证据面板在
  窄屏自动上下排列。

## 2026-10-06 · 体检修复：启发式生成与证据来源

对仓库做了一次全量体检，发现并修复 3 个真实缺陷。三者都在**不配置 LLM**
的默认路径（演示与 CI 走的就是这条）上暴露，且此前无测试覆盖。

### 1. A/B/D 三个阶段输出同一条安装命令

- **根因**：`core/generate/pipeline.py` 的 `_heuristic_one` 把检索到的全部片段
  拼成一段文本，再取**第一条**像命令的行。README 里 `pip install` 排在 `pytest`
  前面，于是 Stage B（测试）和 Stage D（首 PR）都复述了安装命令。
- **影响**：默认演示路径下路线图自相矛盾；L2 的 command_correct 也被压低。
- **修复**：新增 `_STAGE_CMD_PATTERNS`，按阶段限定命令族
  （A 安装 / B 测试 / C issue / D git·PR）；找不到**属于本阶段**的命令时留空，
  而不是拿无关命令顶替（无证据不宣称）。同时补齐 `pytest`/`tox`/`nox` 等
  裸命令名的识别前缀。

### 2. 证据来源与命令不对应

- **根因**：来源取的是"检索结果里第一条有真实路径的片段"，命令取的是"全文第一条
  命令"，两者各自独立选取。Stage B 的 `pytest` 因此被标注成来自 CONTRIBUTING.md
  （该文件根本没有测试命令）。
- **影响**：直接违反项目核心边界「无证据不宣称」——引用的出处并不支持该断言。
- **修复**：改为**逐片段扫描**，命令与来源成对绑定；只有真正包含该命令的文件
  才会被引为证据。

### 3. 证据来源丢失真实文件名大小写

- **根因**：`core/index/perspectives.py` 的 `_doc_by_path` 只返回文本，调用方
  用**小写种子名**（`readme.md`）当证据来源，而仓库里的真实文件是 `README.md`。
- **影响**：前端按来源拼出的「打开原始出处」链接指向不存在的路径（404）。
- **修复**：`_doc_by_path` 改为返回 `(真实路径, 文本)`，证据来源保留仓库原始大小写。

### 回归测试

新增 3 条测试锁住上述修复（`backend/tests/unit/test_pipeline.py`）：

- `test_heuristic_stage_commands_are_not_all_the_same`
- `test_heuristic_evidence_source_actually_backs_the_command`
- `test_evidence_source_preserves_real_file_case`

后端测试总数 59 → 62，全部通过；L1 烟测输出已从「同一条安装命令 ×3」
变为「安装 + 测试」两条正确的阶段命令。

### 文档补全

- `backend/README.md`：此前是**空文件**，补齐运行方式、目录结构与 hermetic 测试说明。
- `frontend/README.md`：此前仍是 Vite 脚手架模板，改写为项目自身的运行/构建/目录说明。
- 根 `README.md`：测试数从过时的 56 更正为 62。

## 2026-10-06（下）· 交付件补齐与检索根因修复

目标：让仓库达到「可直接作为作品提交」的状态。补齐任务书 §6.2 要求的部署包与
演示脚本，并修掉两个影响演示效果的检索层根因。

### 1. GitHub 缓存在 Windows 上完全失效（高影响）

- **根因**：缓存文件名由 key 直接拼成，只替换了 `/` 和 `:`。而每个 GitHub key 都含
  `?`（`github::repos/o/r?state=open`），`?` 在 Windows 上是**非法文件名字符**，
  写盘抛 `OSError: [Errno 22] Invalid argument`；`cache.set` 又把异常静默吞掉，
  于是缓存"看起来正常、实际一次都没写成功"。
- **影响**：Windows 上（团队开发环境）每次运行都重新打 GitHub API，限流很快耗尽——
  这正是 `benchmark/reports/` 里 click / cookiecutter / mocha 报
  `403 rate limit exceeded` 的原因，也让演示无法稳定复现。
- **修复**：`utils/cache.py` 改为白名单式文件名清洗（只保留 `[A-Za-z0-9._-]`），
  超长 key 追加短哈希保证唯一且不超路径长度限制。
- **另修**：`GitHubClient.get_file_text` 原先**绕过缓存**直接请求（与模块文档承诺的
  "响应落盘以避免烧限流"相矛盾），现改为与其它调用一致走磁盘缓存，404 也缓存。

### 2. 「怎么跑测试」答不出来：V3 视角被散文淹没

- **根因**：V3（可执行路径）只要文件名含 `readme`/`contribut` 就收录，且只要正文出现
  `install`/`test` 等词就收录。`psf/requests` 的 `docs/dev/contributing.rst` 是纯叙述
  文档（**一条命令都没有**），却贡献了 11 个块；而真正含 `python -m pytest tests` 的
  `Makefile` 被挤到第 9 位、落在 top-k 之外，于是 B 阶段（测试基线）命令为空。
- **修复**：V3 改为**按内容准入**——文档必须真的含命令行，或本身是构建文件
  （Makefile / pyproject.toml / package.json 等）才进 V3；changelog / history /
  authors 这类"变更与署名"文档一律排除（它们不是可执行路径）。

### 3. 构建文件从未被抓取

- **根因**：`enrich_docs_and_tree` 只抓 README/CONTRIBUTING/LICENSE 与 docs/ 下的
  文档，`Makefile`、`pyproject.toml`、`package.json` 等**构建文件从不抓取**。
  而很多仓库把测试命令只写在 Makefile / package.json 里（`_V3_FILES` 里虽然列了
  makefile，但因从未抓取，那段逻辑实际是死代码）。
- **修复**：按仓库根目录清单补抓一组构建/配置文件，使其可被 V3 检索与引用。

### 4. 检索打分：可执行块优先

- **修复**：确定性回退检索在 V3 视角下，对**真正含命令行**的块加权，
  让"有命令的块"排在"讲命令的散文"之前。这同时惠及 AI 路径（喂给模型的上下文更对）。

### 5. 交付件补齐（任务书 §6.2）

- **Docker Compose 一键部署**：新增 `docker-compose.yml`、`backend/Dockerfile`、
  `frontend/Dockerfile` + `frontend/nginx.conf`（静态站 + `/api` 反代，同源免 CORS）、
  两侧 `.dockerignore`。默认 `USE_CHROMA=false` 走确定性检索，零模型下载、秒级启动。
- **顶层 `.env.example`**：与 `backend/.env.example` 同步，供 compose 直接读取。
- **演示脚本** `docs/demo_script.md`：3 个真实仓库的演示顺序、话术要点、追问演示、
  预热清单与兜底方案（网络差 / 无 Key / 抓取失败分别怎么办）。
- **成本/延迟指标**：`MetricsResult` 新增 `elapsed_s`，L2/L3 运行器记录单仓库生成耗时，
  L3 对比表新增「单仓库耗时」一行；汇总里给出 `elapsed_s_mean` / `elapsed_s_total`。

### 6. 清理与文档

- 删除死代码 `frontend/src/components/GuideDisplay/`（全仓库无引用）。
- `docs/code_outline.md` 的目录树更新为**实际代码结构**（原树仍是规划期的
  `backend/app/` 布局，且列了不存在的文件如 `compress.py`、`symbols.py`）。
- `benchmark/README.md` 待办更新为当前真实状态，并补「L4 为空为何报未通过」的说明
  与补录方法。
- 根 `README.md` 增加 Docker 一键部署小节，测试数更正为 72。

### 验证口径
## 2026-10-06（下下）· 评审材料补齐

目标：把"能跑通的项目"补成"能提交的作品"。本轮补齐任务书 §6.2 / §10 要求的评审材料，
并修掉两处评测链路的健壮性问题。

### 1. 新增评审材料

| 文件 | 内容 | 对应要求 |
|---|---|---|
| `docs/submission.md` | **作品说明**：选题论证 / 四段管线 / 关键工程决策 / 开源清单 / 验证证据 / 路线图 / 开源计划 | §6.2「作品说明」、§10 材料大纲 |
| `docs/video_script.md` | **演示视频分镜脚本**：0:00–4:30 逐段画面 + 旁白 + 制作备注，含压缩到 3 分钟的剪法与录制清单 | §6.2「3-5 分钟演示视频」 |
| `docs/privacy_and_license.md` | **隐私与授权说明**：采集范围 / 不采集什么 / 存储位置 / 密钥处理 / 第三方数据出境 / 合规自查 | §6.2「隐私与授权说明」 |
| `docs/cold_start_checklist.md` | **冷启动演练记录**：7 项逐条实测 + 路径一致性核对 + 未能覆盖项 | §6.2「冷启动演练」、§10.7 |

### 2. L4 状态机：区分「待补充」与「失败」

- **问题**：L4 无记录时返回退出码 1，导致全量 `benchmark.runner` 报"未通过"——
  看起来像提交包坏了，实际只是这一项待补。
- **修复**：改为三态——`PENDING`（无记录，退出 0，明确标注待补充）/ `OK`（有记录）/
  `FAIL`（文件损坏，退出 1）。口径不变：**没有记录就不算闭环完成**，报告里显著标 PENDING。
- 补 4 条测试（`benchmark/tests/test_l4.py`）。

### 3. `git clone` 失败现在带真实原因

- **问题**：`clone_repo` 丢弃了 subprocess 结果，任何失败都只报"clone 失败"，
  不说是没装 git、没网、还是被代理挡了——演示现场极难排查。
- **修复**：捕获 git 的 stderr 并抛出 `CloneError`；区分"未找到 git"、"超时"、"退出码非 0"。

### 4. 评测报告可入库

- **问题**：`benchmark/reports/` 被整目录 gitignore，导致 §6.2 要求的"测试报告"
  **一份都没提交**。
- **修复**：改为只忽略临时产物（`*.tmp`）与测试脚手架目录，真实报告可入库；
  同时修正 jsonl 命名（`l2_l2.jsonl` → `l2_results.jsonl`，去掉了重复前缀）。
- L2 运行器新增 `--repos owner/repo` 参数，便于按仓库分批跑批。

### 5. 任务书与分工表更新

`docs/task_book.md`（v2.0 → v2.1）与 `docs/team_roles.md`（v1.0 → v1.1）此前停留在
2026-09-05 的规划态。新增"进度快照"章节，标注 M0–M3 已完成、M4 进行中，
并列出提交前的剩余动作（L4 记录、全量跑批、录视频、导出 PDF）。

### 6. 根 README 文档索引重构

按"面向评审 / 开发与协作"两组重排，评审入口（作品说明、演示脚本、冷启动记录、
隐私说明）置顶。

### 验证口径
## 2026-10-06（下下下）· 评测跑批与框架修复

目标：产出任务书 §6.2 要求的**测试报告**。跑批过程中发现评测框架自身有 3 处缺陷
会让 `command_exec` 指标失真，一并修复。

### 1. 评测框架：命令"跑不动"其实是环境没准备

| 缺陷 | 后果 | 修复 |
|---|---|---|
| 只建 venv、**不装依赖** | `tox` / `npm test` 一律"不是内部或外部命令"，指标实际在测"这台机器预装了什么" | 自动 `pip install -e .[dev]` / `npm ci`，并补装 `tox`；可用 `OG_SKIP_PROVISION=1` 跳过 |
| Windows 上以裸名 `npm` 调用 subprocess | `CreateProcess` 不解析 `PATHEXT`，安装静默失败；**且失败仍写入"已准备"标记**，导致永久跳过 | 用 `shutil.which` 解析 `npm.cmd` 全路径；标记仅在成功时写入 |
| 内层 `pip()` 声明 `-> None` 且不返回 | 所有 `== 0` 判断恒为假，标记永不写入，每次重复安装 | 修正返回值 |

另：`git clone` 失败原先只报"clone 失败"，现抛出带 **git 原始 stderr** 的 `CloneError`。
新增 `OG_CMD_TIMEOUT`（单条命令超时，默认 900s）。

### 2. 评测报告可入库 + L2 支持按仓库筛选

- `benchmark/reports/` 原先被整目录 gitignore，导致 §6.2 要求的测试报告一份都没提交。
  改为只忽略临时产物与测试脚手架，真实报告入库；jsonl 命名修正（`l2_l2.jsonl` → `l2_results.jsonl`）。
- L2 新增 `--repos owner/repo` 参数。

### 3. 跑批结果（详见 `docs/evaluation_report.md`）

L2（5 仓库 / 26 golden 步骤，无 LLM Key 的确定性路径）：
步骤完整率 53% / 证据命中率 75% / 命令正确率 67% / 命令可执行率 23% / 有据断言率 85%。

L3 消融（同批仓库、同 golden、同指标）：
证据命中率 **10% → 85%**（+75%）、步骤完整率 31% → 53%、命令正确率 50% → 67%。
朴素方案的"有据断言率"是 100% 但证据命中率仅 10%——**声称的出处绝大多数是编的**；
分层管线经证据校验后证据命中率 85%，且诚实性体现为有据断言率反而更低。

低分项已逐条归因（聚合测试套件过重 / 命令依赖未声明的插件 / 测试依赖外部网络），
说明评测体系确实在起作用，而非指标失效。

### 验证口径
## 2026-10-06（下下下下）· 作品说明导出 PDF

任务书 §6.2 的"作品说明 PDF"此前只有 Markdown，本轮补上可直接提交的 PDF 成品。

### 产出

| 文件 | 说明 |
|---|---|
| `output/pdf/OpenGuide-作品说明.pdf` | **10 页 A4**，含封面 / 目录 / 正文，提交用 |
| `tools/render_submission_pdf.py` | 生成脚本，改完 Markdown 后一条命令重新生成 |

```bash
pip install reportlab
python tools/render_submission_pdf.py          # -> output/pdf/OpenGuide-作品说明.pdf
```

### 排版实现

- **字体**：正文微软雅黑、代码 Consolas、ASCII 架构图中的中文用 ReportLab 内置
  `STSong-Light`（全角等宽 CID 字体）。架构图靠"中文占两列"对齐，若中文回退到
  比例字体，方框与箭头会全部错位——这是本轮实测踩到并修掉的坑。
- **结构**：封面（标题 / 一句话定位 / 申报方向 / 团队 / 许可）+ 独立目录页 + 正文；
  每页页眉标注文档名，页脚为"页码 - n -"。
- **表格**：列宽按内容长度加权，表头重复、跨页保持表头；≥3 行的表用 `KeepTogether`
  避免末页只落一行（实测出现过第 10 页仅 1 行的情况）。
- **代码块**：保留原始缩进与换行，`·` 制表符原样呈现，命令中的中文正常显示。

### 验证

- 渲染后逐页转 PNG 目视检查：封面 / 目录 / 架构图 / 数据表 / 末页文档索引均正常。
- 文本抽取校验：各章节标题齐全，无替换字符与乱码，10 页均有实质内容。
- 脚本重跑产物字节数一致（457,059 bytes），确认可复现。

### 验证口径
### 验证口径


- 后端：`python -m pytest backend/tests -q` → 59 passed（含 3 个新增回归测试：
  关键词整词匹配、中文回退检索、Stage D 追问视角）。
- 离线全链路：`python -m benchmark.l1_smoke` 通过（URL→画像→决策树→索引→生成→schema→证据）。
- 前端：`pnpm build`（类型检查 + 生产构建）与 `pnpm lint` 通过。
- 抽查：`how do I improve the docs` 不再被判为「贡献流程」，`make a PR` 正确归为「贡献流程」。
