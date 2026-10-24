# 收尾验收记录 · 2026-10-24

核心提交 b4dfc86。当前版本 336 后端/评测、58 前端测试通过，构建及 lint 通过。GitHub CI 五项全部成功，含容器及同源接口；完整提交号、任务与链接见 ci-status.json。新目录原生安装与无凭据 HTTP 记录在 clean-start.json，缓存被复用；首次父目录 pnpm --dir 选择错误版本的情况未隐去。

## 数据与边界

- multi-repo-audit.json：当前规则管线检查五个固定仓库。结构和来源约束通过不等于整个新手流程可运行；缺失命令和未知目录保留。
- upstream-command-rerun.json：复用已有专用环境及 AI 源码审阅计划。Click 直接 pytest 通过；Requests 全量 5 失败、626 通过，子集 24 通过。生成命令、审阅者替代命令和子集不混算。
- model-comparison.json：22cd0e9 的严格对照尝试，预期 16 组、0 可计分，15 次尝试/3 响应/5781 服务报告 tokens；不证明质量优势，独立人工复核 pending。早于之后的条件性安装修复。
- live-ai-product-validation.json 与对应 guide：b4dfc86 的真实产品请求，每阶段 25 秒等待，35.686 秒返回，但各阶段全部规则回退，不是 AI 成功。
- live-rule-guide-before-conditional.json：网页最初实际下载的规则指南，明确属于修复前输入/问题样例。更新后的条件性提示由 conditional-install.txt/PNG 及产品实际返回记录核对，不倒改旧导出。
- live-rule-qa.md：通过界面实际下载的单轮仅原文问答；没有调用问答模型。
- third-party-resources.json：锁定版本、官方包元数据及材料工具信息；许可义务/服务条款与团队审阅仍 pending。
- video-validation.json / pdf-validation.json：视频全片解码、实际时长和文档页面/边界检查。它们不是内容真实性或团队审核认证。

页面取景来自本轮浏览器验收，保留生成模式、固定出处、缺失数据及空白执行记录。没有填入用户个人学习摘要、原始日志、真实 API 密钥或伪造 PR。取景后恢复了用户原指南和手动进度。页面配置保存仅用无效测试值，没有向该测试端点发起模型请求；随后刷新并重启后端清除了测试配置。

原始第三方文本、提示、响应、安装日志和完整实跑日志留在 Git 忽略目录。本目录只公开必要的页面证据、导出与脱敏统计；其范围不代替真人试用、独立人工复核或团队授权审阅。
