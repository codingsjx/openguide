"""Build a clearly labelled 4-minute screenshot replay, never a fake live demo.

Requires Pillow and ffmpeg (for example imageio-ffmpeg's bundled executable).
python tools/render_demo_replay.py --ffmpeg <path-to-ffmpeg>
Screenshots must already have been captured through browser acceptance.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'output/qa/release-20261024'
SCENES = [
    ('从读懂仓库，到准备首次贡献', 'home.png', '目标用户是开源新手。\n本片使用实际页面验收截图回放。\n不是实时完整录屏，也没有真人试用数据。'),
    ('先核对原文安装入口', 'install.png', '规则模式从仓库资料整理操作。\n核对组件和执行目录，再复制命令。\n本片没有代用户执行安装。'),
    ('条件性功能，不变成必装项', 'conditional-install.png', '原文明示需要向量功能时，才启用 extras。\n页面标注可选条件。\n不将其加入默认测试的必做前置步骤。'),
    ('看不懂为什么：解释与原文分开', 'explain.png', '常见命令有通用工具说明及官方链接。\n当前命令附近的原文单独展示。\n不猜测维护者的选型原因。'),
    ('测试、构建与局部范围分开', 'tests.png', '保留前置安装、执行目录和输入路径。\n记录失败、跳过和未选中项。\n构建成功不代表完整测试通过。'),
    ('实际结果由用户如实填写', 'records.png', '执行记录不自动填成功。\n学习状态与执行情况独立。\n本机保存与导出不构成独立真实性证明。'),
    ('没有候选，也有下一步', 'task.png', '采样未取得任务，不等于仓库没有任务。\n打开最新讨论核对状态。\n人工选题需记录来源、复现与验收范围。'),
    ('有实际改动，再整理 PR 草稿', 'draft.png', '没有修改文件与改动说明时，草稿保持待补充。\n用户记录的验证结果仍待核对。\n不会自动向 GitHub 提交。'),
    ('贡献问答：先看回答，再核对出处', 'qa.png', '本画面为仅原文模式，没有调用问答模型。\n后端测试目录由原文上下文推导。\n可以继续追问并下载记录。'),
    ('模型配置按页面会话隔离', 'session-settings.png', '页面配置只在有界、过期的后端内存保留。\n其他页面不继承个人覆盖。\n公网认证、配额和 TLS 仍由部署者另配。'),
    ('验证结果按范围报告', None, '本轮工程回归与真实命令复跑分别记录。\n失败结果不能改写为通过。\n模型对照未取得可计分结果。'),
    ('开放成果与仍需完成的审核', None, '源码、脚本、锁文件、报告和脱敏统计可查。\n独立人工复核、真人效果和团队授权审核仍待完成。\n本片为演示候选稿，提交前需团队实际审阅。'),
]


def wrap(text, width, font, draw):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for char in paragraph:
            if line and draw.textlength(line+char,font=font)>width and char not in '，。；：？！、）”》':
                lines.append(line);line=char
            else:line+=char
        lines.append(line)
        lines.append('')
    return lines


def build(ffmpeg: Path, output: Path):
    frames=ROOT/'_run_cache/release-20261024/video-frames';frames.mkdir(parents=True,exist_ok=True)
    regular=Path(r'C:\Windows\Fonts\msyh.ttc');bold=Path(r'C:\Windows\Fonts\msyhbd.ttc')
    title_font=ImageFont.truetype(str(bold),32);body=ImageFont.truetype(str(regular),24);small=ImageFont.truetype(str(regular),19)
    sources=[]
    for i,(title,filename,caption) in enumerate(SCENES,1):
        frame=Image.new('RGB',(1600,900),'#f1f6f5');draw=ImageDraw.Draw(frame)
        draw.rectangle((0,0,1600,76),fill='#154e45')
        draw.text((28,18),f'OpenGuide  |  {title}',font=title_font,fill='white')
        draw.rounded_rectangle((1208,94,1572,784),radius=12,fill='white')
        if filename:
            path=EVIDENCE/filename
            screenshot=Image.open(path).convert('RGB')
            screenshot=ImageOps.contain(screenshot,(1160,686))
            frame.paste(screenshot,(24,104+(686-screenshot.height)//2))
            sources.append({'file':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        else:
            draw.rounded_rectangle((24,104,1184,790),radius=12,fill='white')
            entries = [
                '336 项后端 / 评测回归；58 项前端检查',
                'b4dfc86：GitHub CI 五项任务均成功（含容器）',
                'Click：2179 通过、107 跳过、31000 未选中',
                'Requests 完整 recipe：626 通过、5 失败',
                '严格模型对照：16 预期组、0 可计分组',
                '这些记录不等于新手成功率或国奖保证',
            ] if i==11 else [
                '公开代码：https://github.com/codingsjx/openguide',
                '当前评测、隐私说明与第三方资源清单已同步',
                '实际模型/命令失败及未测范围保留',
                '待完成：独立人工复核、真人效果、团队审阅授权',
                '页面验收回放版；无配音；非实时完整录屏',
                '请团队审核后再作为参赛材料提交',
            ]
            for n,line in enumerate(entries):
                draw.text((58,155+n*90),line,font=body,fill='#203d36')
        y=126
        for line in wrap(caption,312,body,draw):
            draw.text((1232,y),line,font=body,fill='#203d36');y+=35
        draw.text((1232,712),f'{i:02} / 12 · 每章 20 秒',font=small,fill='#59716c')
        draw.rectangle((0,816,1600,900),fill='#e1ede9')
        draw.text((28,832),'页面验收截图回放版 · 非实时完整录屏 · 原文匹配不等于命令已执行',font=small,fill='#294e44')
        draw.text((28,864),'2026-10-24 · 无真人试用或上游接受率结论 · 详细范围见当前评测报告',font=small,fill='#59716c')
        frame.save(frames/f'frame-{i:02}.png')
    playlist=''.join(f"file 'frame-{i:02}.png'\nduration 20\n" for i in range(1,13))+"file 'frame-12.png'\n"
    (frames/'frames.txt').write_text(playlist,encoding='utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run([str(ffmpeg),'-y','-f','concat','-safe','0','-i','frames.txt','-t','240','-r','10','-c:v','libx264','-preset','medium','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',str(output.resolve())],cwd=frames,capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Video encoding failed; see local render log')
    (frames/'encode.log').write_text(result.stderr,encoding='utf-8')
    probe=subprocess.run([str(ffmpeg),'-i',str(output.resolve())],capture_output=True,text=True)
    match=re.search(r'Duration: (\d\d):(\d\d):(\d\d\.\d+)',probe.stderr)
    if not match:raise RuntimeError('Could not verify encoded duration')
    duration=int(match[1])*3600+int(match[2])*60+float(match[3])
    manifest={'date':'2026-10-24','kind':'labelled-screenshot-replay-not-live-recording','planned_duration_seconds':240,'duration_seconds':duration,'width':1600,'height':900,'fps':10,'audio':False,'sources':sources,'chapters':[{'start_s':20*i,'title':scene[0]} for i,scene in enumerate(SCENES)],'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'team_final_review':'pending'}
    output.with_suffix('.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'video':str(output),'bytes':manifest['bytes'],'duration_seconds':duration},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'output/video/OpenGuide-页面验收回放.mp4')
    args=parser.parse_args();build(args.ffmpeg,args.output)
