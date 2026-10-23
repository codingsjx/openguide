import { ArrowRightOutlined, FileTextOutlined, GithubOutlined, LinkOutlined } from '@ant-design/icons'

const stages = [
  { letter: 'A', title: '搭好环境', detail: '找到安装入口' },
  { letter: 'B', title: '跑通测试', detail: '核对命令与目录' },
  { letter: 'C', title: '选择任务', detail: '确认范围与状态' },
  { letter: 'D', title: '准备 PR', detail: '遵循贡献约定' },
]

export default function LandingJourney() {
  return <div className="journey-visual" aria-label="从仓库原文到贡献路线的流程示意">
    <div className="journey-window">
      <div className="journey-window-bar"><span className="window-dots"><i /><i /><i /></span><span>你的开源旅程</span><GithubOutlined /></div>
      <div className="journey-repository"><span className="journey-repo-icon"><GithubOutlined /></span><div><strong>一个你感兴趣的仓库</strong><span>从这里，找到第一步。</span></div><span className="illustration-label">流程示意</span></div>
      <div className="journey-source"><span><FileTextOutlined /> 仓库原文</span><div><span>项目说明</span><span>开发与测试</span><span>贡献约定</span></div></div>
      <div className="journey-connector"><span />整理为可行动的路线<ArrowRightOutlined /><span /></div>
      <div className="journey-stages">{stages.map((stage) => <div key={stage.letter}><b>{stage.letter}</b><strong>{stage.title}</strong><span>{stage.detail}</span></div>)}</div>
      <div className="journey-footnote"><LinkOutlined /><span>每一步，都能回到原文核对</span></div>
    </div>
    <div className="journey-floating-note"><span className="note-icon"><FileTextOutlined /></span><div><strong>让建议有据可查</strong><span>资料不足，也会清楚告诉你</span></div></div>
  </div>
}
