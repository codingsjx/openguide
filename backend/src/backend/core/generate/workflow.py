"""Conservative execution context and ordering, independent of model claims.

Build-file recipes inherit their build file's directory. Documentation-only
commands keep an unknown directory rather than assuming every README means
repository root. This checks paths, not tool availability or runtime success.
"""
from pathlib import PurePosixPath
import re

from backend.core.generate.schemas import GuideStep
from backend.core.github.recon import RawSignals
from backend.core.generate.command_context import input_paths as _input_paths, document_directory, command_family

_LABELS = {"A": "环境搭建", "B": "测试基线", "C": "挑选 issue", "D": "首次 PR 路径"}
_CLONE = re.compile(r"^git clone\b")
_INSTALL = re.compile(r"^(?:python(?:3)? -m pip install|pip(?:3)? install|uv (?:sync|pip install)|npm (?:ci|install)|pnpm install|yarn install)\b")
_ENVIRONMENT = re.compile(r'^(?:uv venv|python(?:3)? -m venv|virtualenv|conda (?:create|env create))(?=\s|$)')


def prepare_workflow(sig: RawSignals, steps: list[GuideStep]) -> list[GuideStep]:
    prepared = [step.model_copy(deep=True) for step in steps]
    for step in prepared:
        if step.command and _CLONE.match(step.command) and step.stage != "A":
            step.original_stage = step.stage
            step.stage = "A"
            step.stage_label = _LABELS["A"]
    prepared.sort(key=lambda s: ("ABCD".index(s.stage), 0 if s.command and _CLONE.match(s.command) else 1))
    unique, clone_commands = [], set()
    for step in prepared:
        if step.command and _CLONE.match(step.command) and step.evidence.verification == "command_verified":
            if step.command in clone_commands:
                continue
            clone_commands.add(step.command)
        unique.append(step)
    has_clone = any(s.command and _CLONE.match(s.command) and s.evidence.verification == 'command_verified' for s in unique)
    has_test = any(s.stage == 'B' and s.command and s.evidence.verification == 'command_verified' for s in unique)
    prepared = [s for s in unique if not (
        not s.command and s.evidence.kind == 'missing' and (
            (has_clone and s.stage == 'A' and re.fullmatch(r'(?:准备|进行|执行)(?:\s*Git\s*)?克隆仓库', s.title, re.I)) or
            (has_test and s.stage == 'B' and re.fullmatch(r'(?:确认|核对)测试基线(?:期望|预期)(?:结果)?', s.title))
        ))]
    for i, step in enumerate(prepared, 1):
        step.step_id = i
        step.stage_label = step.stage_label or _LABELS[step.stage]
    known = set(sig.file_tree) | {doc.path for doc in sig.doc_files}
    directories = {"."}
    for path in known:
        directories.update(str(parent) for parent in PurePosixPath(path).parents)
    clone_ids, environment_steps, install_steps = [], [], []
    for step in prepared:
        step.working_directory = None
        step.directory_basis = "unknown"
        step.required_paths, step.missing_inputs = [], []
        step.prerequisite_step_ids, step.context_notes = [], []
        step.success_checks = []
        command = step.command
        if not command:
            continue
        step.success_checks.append("命令正常结束且退出码为 0；这只是基础执行检查，不代表功能效果已经验证。")
        if step.stage == "B" and not re.match(r'^(?:pnpm|npm|yarn)\s+(?:run\s+)?build(?=\s|$)', command):
            step.success_checks.append("核对测试输出中的失败、跳过与未选中项，并确认实际运行了预期用例。")
        if _CLONE.match(command):
            step.directory_basis = "clone_destination"
            step.context_notes.append("在你选择的项目存放目录执行；克隆结束后再进入新建的仓库目录。")
            clone_ids.append(step.step_id)
            if step.original_stage:
                step.context_notes.append("该克隆步骤已从后续阶段移到安装之前；这是流程排序调整。")
            continue
        step.prerequisite_step_ids = list(clone_ids)
        source = step.evidence.source.split("#", 1)[0]
        path = PurePosixPath(source)
        build_doc = next((doc for doc in sig.doc_files if doc.path == source), None)
        if step.evidence.verification == "command_verified" and build_doc and path.name in {"Makefile", "makefile", "GNUmakefile"}:
            step.working_directory = str(path.parent)
            step.directory_basis = "build_file"
            step.context_notes.append("按在该 Makefile 所在目录运行的常见约定推导；请核对原文中的 -C/-f、子项目说明及运行时依赖。")
        elif step.evidence.verification == 'command_verified' and (context := document_directory(sig, source, command, step.evidence.line_start)):
            step.working_directory, note = context
            step.directory_basis = 'document_context'
            step.context_notes.append(note)
        else:
            step.context_notes.append("尚未确认执行目录；请先查看来源中的 cd、项目根目录或子项目说明。")
        if step.working_directory is not None:
            for value, allow_directory in _input_paths(command):
                if re.match(r"^[A-Za-z]:|^[\\/]", value) or "://" in value or ".." in PurePosixPath(value).parts or re.search(r"[*?${}]", value):
                    step.context_notes.append("命令含不能静态核对的输入路径，请结合原文确认。")
                    continue
                full = str(PurePosixPath(step.working_directory) / value)
                step.required_paths.append(full)
                if full not in known and not (allow_directory and full in directories):
                    if sig.file_tree and "tree" not in sig.unavailable_signals:
                        step.missing_inputs.append(full)
                    else:
                        step.context_notes.append(f"文件树未完整取得，尚不能确认输入路径：{full}")
        if step.stage == 'A' and _INSTALL.match(command):
            step.prerequisite_step_ids.extend(s.step_id for s in environment_steps
                if step.working_directory is not None and s.working_directory==step.working_directory
                and command_family(s.command)==command_family(command))
        if step.stage == "B":
            matching_installs=[s for s in install_steps if step.working_directory is not None
                and s.working_directory==step.working_directory and command_family(s.command)==command_family(command)]
            matching_environments=[s for s in environment_steps if step.working_directory is not None
                and s.working_directory==step.working_directory and command_family(s.command)==command_family(command)]
            step.prerequisite_step_ids.extend(s.step_id for s in matching_environments+matching_installs)
            if not matching_installs:
                step.context_notes.append("尚未确认与本步骤组件和目录匹配的安装入口，请先核对该组件的开发依赖。")
        if step.stage == "A" and _INSTALL.match(command):
            install_steps.append(step)
        if step.stage == 'A' and _ENVIRONMENT.match(command):
            environment_steps.append(step)
    return prepared
