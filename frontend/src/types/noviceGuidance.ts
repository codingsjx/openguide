// General learning references; never presented as the selected repo's rules.
export const learningReferences = [
  { title: 'Open Source Guides：如何为开源做贡献', url: 'https://opensource.guide/zh-hans/how-to-contribute/' },
  { title: 'GitHub：从 Fork 到 Pull Request', url: 'https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project' },
  { title: 'CPython：小范围修改、验证与审阅流程（项目示例）', url: 'https://devguide.python.org/getting-started/pull-request-lifecycle/' },
]
export const taskDirections = {
  bug: { label: '复现一个问题', start: '先按仓库说明运行，记录实际现象、预期行为和最小复现；未复现时先保持调查状态。', check: '验收写清同一复现步骤在改前与改后的表现，并记录相关回归检查范围。' },
  docs: { label: '改进入门文档', start: '实际走一遍安装或使用流程，找到可具体指出的缺失、歧义或失效示例；先核对项目是否接受该类修改。', check: '验收写清哪一段说明应能被照做，需核对命令、链接或文档构建；没有发现问题时先记录观察。' },
  tests: { label: '补充行为测试', start: '先确认一个已有行为及其预期，查看项目现有测试写法；不要假定没有测试或擅自改变行为。', check: '验收写清新增用例覆盖的条件与实际结果，再核对项目要求的相关测试范围。' },
  other: { label: '其他小范围贡献', start: '从你实际使用时遇到的一个具体需求入手，先搜索现有 issue/PR，并确认维护者参与规则。', check: '定义一个可观察的结果和本次不处理的范围；需要讨论时先记录待确认项。' },
} as const
