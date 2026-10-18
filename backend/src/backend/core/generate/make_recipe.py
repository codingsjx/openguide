"""Expand a single, literal Makefile target without invoking make or a shell.

Only targets without prerequisites and with exactly one plain recipe are
supported. Variables, continuations, target-specific assignments and compound
shell syntax are rejected; this is not a general Make interpreter.
"""
import re

from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.recon import RawSignals


def expand_make_recipe(step: GuideStep, sig: RawSignals) -> GuideStep:
    command = step.command or ""
    match = re.fullmatch(r"make ([A-Za-z0-9_.-]+)", command)
    if not match or step.stage not in {"A", "B"}:
        return step
    source = step.evidence.source.split("#", 1)[0]
    doc = next((d for d in sig.doc_files if d.path == source and d.name in {"Makefile", "makefile", "GNUmakefile"}), None)
    if doc is None:
        return step
    target = match[1]
    lines = doc.text.splitlines()
    if any(re.match(r"^(?:-?include\b|sinclude\b|define\b|endef\b|ifeq\b|ifneq\b|ifdef\b|ifndef\b|export\b|unexport\b|\.ONESHELL\s*:|\.RECIPEPREFIX\s*[:?+]?=|SHELL\s*[:?+]?=|\.SHELLFLAGS\s*[:?+]?=)", line) for line in lines):
        return step
    headers = [i for i, line in enumerate(lines) if re.match(rf"^{re.escape(target)}\s*:", line)]
    if len(headers) != 1:
        return step
    start = headers[0]
    if not re.fullmatch(rf"{re.escape(target)}\s*:\s*(?:#.*)?", lines[start]):
        return step
    recipes = []
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith("\t"):
            break
        recipes.append(line.strip())
    if len(recipes) != 1:
        return step
    recipe = recipes[0]
    if any(c in recipe for c in ("$", "\\", ";", "|", "&", "<", ">", "`")) or recipe.startswith(("@", "-", "+")):
        return step
    result = step.model_copy(deep=True)
    # Running `make target` and directly running its recipe are different
    # invocations. A historical execution record must never transfer silently.
    result.execution_record = None
    result.original_command = command
    result.command_derivation = f"由 {doc.path} 的 {target} 目标展开为单条原文命令（展开过程不执行命令）"
    result.command = recipe
    result.evidence = Evidence(kind="file", source=doc.path, quote=recipe)
    return result
