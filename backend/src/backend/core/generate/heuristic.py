"""Conservative rule fallback: complementary tasks, literal sources, no execution."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from backend.core.generate.evidence import verify_step_evidence
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.generate.command_context import document_directory, input_paths, is_dependency_declaration, command_from_line
from backend.core.generate.prerequisites import runtime_steps

LABELS = {"A": "环境搭建", "B": "测试基线", "C": "挑选 issue", "D": "首次 PR 路径"}


def pending(stage: str, title: str) -> GuideStep:
    return GuideStep(step_id=0, stage=stage, stage_label=LABELS[stage], title=title,
        expected="资料尚不足，请打开仓库文档确认；此项不代表已经完成操作。",
        evidence=Evidence(kind="missing", reason="未取得可核验的对应操作说明"))


def _commands(sig, snippets, pattern):
    seen, result = set(), []
    for snippet in snippets:
        source = snippet.get('source', '')
        if snippet.get('meta_kind', 'file') != 'file':
            continue
        lines = snippet['text'].splitlines() + re.findall(r'`([^`\n]+)`', snippet['text'])
        for line in lines:
            command = command_from_line(line)
            if (not re.match(pattern, command) or is_dependency_declaration(command) or command in seen or len(command) > 300
                    or re.search(r'<[^>]+>|\{[^}]*\}|\$\(|&&|\|\||[;`]', command)
                    or re.search(r'\byour[_-]?(?:user)?name(?:[_-]here)?\b|\byour[-_]org\b', command, re.I)):
                continue
            step = GuideStep(step_id=0, stage='A', title='原文命令', command=command,
                evidence=Evidence(source=source))
            evidence = verify_step_evidence(step, sig)
            if evidence.verification == 'command_verified':
                seen.add(command)
                step.evidence = evidence
                result.append(step)
    return result


def _operation(step, stage, title):
    step.stage, step.stage_label, step.title = stage, LABELS[stage], title
    step.expected = "按原文核对前置条件和执行目录后操作；记录实际退出码与输出，本指南没有执行该命令。"
    return step


def _component_key(sig, step):
    command = step.command
    context = document_directory(sig, step.evidence.source, command, step.evidence.line_start)
    directory = context[0] if context else None
    family = 'javascript' if re.match(r'^(?:npm|pnpm|yarn)\b', command) else 'python' if re.match(r'^(?:python\d?|pip\d?|uv|pytest|tox|nox|poetry|conda|virtualenv)\b', command) else command.split()[0]
    # Different requirements files can represent separate components even
    # when both installation commands run from repository root.
    inputs = input_paths(command)
    if inputs:
        # A prose pip alternative and a fenced uv command can refer to the
        # same requirements file. Prefer the first (with explicit context).
        value = inputs[0][0]
        resolved = str(PurePosixPath(directory or '.') / value)
        if resolved in sig.file_tree:
            return family, 'input_component', str(PurePosixPath(resolved).parent)
    input_parent = inputs[0][0].rsplit('/', 1)[0] if inputs and '/' in inputs[0][0] else ''
    return family, directory, input_parent


def _complementary(sig, candidates, limit):
    output, keys = [], set()
    for step in candidates:
        key = _component_key(sig, step)
        if key not in keys:
            keys.add(key)
            output.append(step)
        if len(output) >= limit:
            break
    return output


def generate_stage(sig, stage, snippets, command_pattern):
    if stage == 'A':
        candidates = _commands(sig, snippets, command_pattern)
        candidates = [s for s in candidates if not s.evidence.source.startswith('.github/workflows/')]
        clone = [s for s in candidates if s.command.startswith('git clone ')]
        environment_commands = [s for s in candidates if re.match(r'^(?:uv venv|python(?:3)? -m venv|virtualenv|conda (?:create|env create))(?=\s|$)', s.command)]
        environment = [s for s in environment_commands if not re.search(r'publish|release|upload|deploy', s.command, re.I)]
        installs = [s for s in candidates if s not in clone and s not in environment_commands]
        installs.sort(key=lambda s: not bool(re.search(r'requirements-dev|(?:^|\s)-e\s|\[.*(?:dev|test)|uv sync|npm ci', s.command)))
        output = [_operation(clone[0], 'A', '按原文克隆仓库')] if clone else [pending('A', '取得本地副本，核对仓库获取方式')]
        if not clone:
            output[0].expected = '仓库原文未提供已核验的克隆说明，可查看下方“通用 Git 起步”。那是工具提供的标准操作提示，仓库特殊获取要求仍需核对。'
        requirements = runtime_steps(sig)
        output.extend(requirements)
        for doc in sig.doc_files:
            config = next((line.strip() for line in doc.text.splitlines()
                if re.fullmatch(r'(?:Copy-Item|cp)\s+\.env\.example\s+\.env', line.strip())), None)
            if config and '.env.example' in sig.file_tree:
                output.append(GuideStep(step_id=0,stage='A',stage_label=LABELS['A'],title='按原文准备本地环境配置',
                    expected='先检查本地配置是否已存在，再按原文复制模板并填写所需配置；不要覆盖已有配置或在聊天、日志中发送密钥。此步骤尚未执行。',
                    evidence=Evidence(source=doc.path,quote=config)))
                break
        if environment:
            output.append(_operation(environment[0], 'A', '按原文创建开发环境'))
        elif not requirements:
            output.append(pending('A', '核对运行时版本与开发环境要求'))
        selected = _complementary(sig, installs, 4)
        output.extend(_operation(step, 'A', '按原文启用前端包管理工具' if step.command.startswith('corepack enable') else '按原文安装依赖（请核对组件及开发用途）') for step in selected)
        if not selected:
            output.append(pending('A', '待确认开发依赖安装方法'))
        return output
    if stage == 'B':
        candidates = _commands(sig, snippets, command_pattern)
        candidates = [s for s in candidates if not re.search(r'(?:^|\s)(?:--version|--help|-V|-h)(?:\s|$)', s.command)]
        candidates.sort(key=lambda s: bool(re.search(r'\b(?:stress|random|coverage|browser)\b|--numprocesses', s.command)))
        builds = [s for s in candidates if re.match(r'^(?:npm|pnpm|yarn)\s+(?:run\s+)?build(?=\s|$)', s.command)]
        tests = [s for s in candidates if s not in builds]
        output = []
        for step in _complementary(sig, tests, 3):
            step = _operation(step, 'B', '按原文运行测试（先核对组件与范围）')
            if re.search(r'\b(?:stress|random|coverage|browser)\b|--numprocesses', step.command):
                step.title = '核对仓库专项测试命令及运行条件'
            elif re.search(r'(?:^|\s)(?:-k|-m|--deselect|--lf|--last-failed)|tests/[^ ]+\.py', step.command):
                step.title = '核对局部测试范围（不等同完整测试基线）'
            output.append(step)
        if not output:
            output.append(pending('B', '待确认测试命令与测试范围'))
        for step in _complementary(sig, builds, 2):
            step = _operation(step, 'B', '按原文进行构建检查（不等同测试）')
            step.expected = '核对组件目录与依赖后进行构建，记录退出码和构建输出；构建成功不等同测试通过，本指南未执行。'
            output.append(step)
        return output
    if stage == 'C':
        issues = [i for i in sig.issues if not i.get('pull_request') and i.get('number') and i.get('state') == 'open']
        issues.sort(key=lambda i: bool(i.get('assignees') or i.get('assignee') or i.get('locked')))
        if issues:
            issue = issues[0]
            return [GuideStep(step_id=0, stage='C', stage_label=LABELS['C'], title='核对候选 issue',
                expected='核对最新状态、讨论和维护者规则后再决定是否参与。',
                evidence=Evidence(kind='issue', source=f"#{issue['number']}", quote=issue.get('title') or ''))]
        step = pending('C', '查看任务检索入口，记录待核对的小范围任务')
        step.expected = '查看任务候选与 GitHub 检索入口；没有候选时可人工选题，记录问题、范围和原始来源，再核对维护者规则。'
        return [step]

    # PR preparation must never disappear when a clone command is moved to A.
    # Match prose only in actual contribution documents, not arbitrary READMEs.
    paths = {s.get('source', '').split('#', 1)[0] for s in snippets}
    docs = [d for d in sig.doc_files if d.path in paths and re.search(r'contribut|pull_request_template', d.path, re.I)]
    categories = [
        ('确认 Fork 与分支要求', r'\bfork\b|\bbranch\b|分支|分叉'),
        ('确认提交前的测试与检查要求', r'\btests?\b|\blint\b|测试|检查'),
        ('确认 PR 提交及模板要求', r'pull request|pull-request|\bPR\b|模板'),
        ('确认审查与社区沟通要求', r'\breview\b|\bdiscuss|审查|讨论|沟通'),
    ]
    output, used = [], set()
    for title, pattern in categories:
        for doc in docs:
            quote = next((line.strip() for line in doc.text.splitlines()
                if 8 <= len(line.strip()) <= 800 and re.search(pattern, line, re.I)
                and line.strip() not in used and not re.match(r'^\s*git clone\b', line)), None)
            if quote:
                output.append(GuideStep(step_id=0, stage='D', stage_label=LABELS['D'], title=title,
                    expected='打开完整贡献规范核对要求；原文摘录不代表已提交或合并 PR。',
                    evidence=Evidence(source=doc.path, quote=quote)))
                used.add(quote)
                break
    if not output:
        output = [pending('D', '待确认仓库 PR 规范与提交要求')]
        output[0].expected = '未取得可核验的仓库专属 PR 规范。可先按下方通用准备清单整理任务、实际改动和测试记录；提交前仍需核对维护者要求。'
    return output
