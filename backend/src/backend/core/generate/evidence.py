"""Evidence verification: "无证据不宣称".

A generated step's `evidence.source` must resolve to something real we actually
fetched from the repo (a doc file, a root build file, or an issue/PR reference).
If it does not, the step's evidence is downgraded to kind="missing" so the
frontend and the benchmark both treat "claimed without a source" as absent.

`verify_step` is shared by generation and by benchmark L2 (evidence_hit) to
keep the audit the same everywhere.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, unquote

from backend.core.github.recon import RawSignals
from backend.core.generate.schemas import Evidence
from backend.core.generate.command_context import is_dependency_declaration, source_command_line, without_shell_comment

# Issue refs like "#42" / "issues/42" / a full github issue url.
_ISSUE_RE = re.compile(r"(?:issues?/)?(\d{1,6})$")
_GH_ISSUE_URL_RE = re.compile(r"github\.com/[^/]+/[^/]+/issues/(\d{1,6})")


def available_sources(sig: RawSignals) -> set[str]:
    """Lowercased repo-relative paths we actually hold (doc files + root build + tree)."""
    paths: set[str] = set()
    for f in sig.doc_files:
        paths.add(f.path.lower())
    paths.update(k for k in sig.root_entries)
    paths.update(p.lower() for p in sig.file_tree)
    return paths


def resolve_evidence_source(source: str, sig: RawSignals) -> Evidence:
    """Return an Evidence with kind set according to whether source is real.

    Handles:
    - repo file path "docs/install.md#L3"  (path must be in available_sources)
    - issue ref "#42" or ".../issues/42"   (must exist in sig.issues numbers)
    - github blob URL fallback -> file path extraction when it matches a file
    """
    avail = available_sources(sig)
    issue_numbers = {
        i.get("number") for i in sig.issues if i.get("pull_request") is None
    }
    src = (source or "").strip()
    if not src:
        return Evidence(kind="missing", source="", quote="")

    if src.startswith(("http://", "https://")):
        url = urlsplit(src)
        prefix = f"/{sig.meta.owner}/{sig.meta.repo}/"
        if url.scheme != "https" or url.netloc.lower() != "github.com" or not url.path.startswith(prefix):
            return Evidence(kind="missing", reason="来源不属于当前 GitHub 仓库")
        relative = unquote(url.path[len(prefix):])
        if relative.startswith("blob/"):
            refs = [sig.meta.default_branch]
            ref = next((r for r in refs if relative.startswith(f"blob/{r}/")), None)
            if not ref:
                return Evidence(kind="missing", reason="来源分支与当前分析分支不符")
            src = relative[len(f"blob/{ref}/"):] + (f"#{url.fragment}" if url.fragment else "")
        elif relative.startswith("issues/"):
            src = relative
        else:
            return Evidence(kind="missing", reason="不支持的仓库来源 URL")

    m = _GH_ISSUE_URL_RE.search(src)
    if m and int(m.group(1)) in issue_numbers:
        return Evidence(kind="issue", source=f"#{m.group(1)}", quote="")

    # Plain "#N" shorthand (no leading path).
    bare = src.strip()
    if bare.startswith("#") and bare[1:].isdigit():
        num = int(bare[1:])
        if num in issue_numbers:
            return Evidence(kind="issue", source=f"#{num}", quote="")
        return Evidence(kind="missing", source=src, quote="")

    # "issues/N" / "pull/N" prefixed refs.
    path_part = src.split("#", 1)[0].strip("/")
    if path_part.startswith(("issues/", "pull/")):
        m2 = _ISSUE_RE.search(path_part)
        if m2 and int(m2.group(1)) in issue_numbers:
            return Evidence(kind="issue", source=f"#{m2.group(1)}", quote="")

    # Treat "#L3"-style suffix: strip, then look up file path.
    norm = src.split(" ", 1)[0].split("#", 1)[0].lower().strip("/")
    # Possible full blob URL: extract /owner/repo/blob/ref/<path>.
    blob = re.search(r"blob/[^/]+/(.+)", src.lower())
    if blob:
        norm = blob.group(1).split("#", 1)[0]

    if ".." in norm.split("/"):
        return Evidence(kind="missing", reason="非法来源路径")
    actual_files = {d.path.lower() for d in sig.doc_files} | {p.lower() for p in sig.file_tree}
    if norm in actual_files:
        actual = next((p for p in [d.path for d in sig.doc_files] + sig.file_tree + list(sig.root_entries.values()) if p.lower() == norm), norm)
        anchor = src.split("#", 1)[1] if "#" in src else ""
        if anchor:
            match = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", anchor)
            doc = next((d for d in sig.doc_files if d.path == actual), None)
            if not match or doc is None:
                return Evidence(kind="missing", reason="无法核验行号")
            start, end = int(match[1]), int(match[2] or match[1])
            if start < 1 or end < start or end > len(doc.text.splitlines()):
                return Evidence(kind="missing", reason="行号越界")
        return Evidence(kind="file", source=actual + (f"#{anchor}" if anchor else ""), verification="source_exists")
    return Evidence(kind="missing", source=src, quote="")


def verify_step_evidence(step, sig: RawSignals) -> Evidence:
    """Verify provenance and literal support; never claim semantic entailment.

    A file existing is distinct from its text supporting a command. Commands
    must occur verbatim in the cited text/line range; unrelated search hits
    cannot repair them. No command is executed by this verifier.
    """
    ev = resolve_evidence_source(step.evidence.source, sig)
    if ev.kind == "missing":
        return ev
    if ev.kind == "issue":
        issue = next(i for i in sig.issues if str(i.get("number")) == ev.source.lstrip("#"))
        text = f"{issue.get('title', '')}\n{issue.get('body') or ''}"
        ev.verification = "source_exists"
        if step.stage == "C" and issue.get("state", "open") != "open":
            return Evidence(kind="missing", reason="任务已关闭")
    else:
        path = ev.source.split("#", 1)[0]
        doc = next((d for d in sig.doc_files if d.path == path), None)
        text = doc.text if doc else ""
        if "#" in ev.source:
            anchor = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", ev.source.split("#", 1)[1])
            ev.line_start, ev.line_end = int(anchor[1]), int(anchor[2] or anchor[1])
            text = "\n".join(text.splitlines()[ev.line_start - 1:ev.line_end])
    quote = step.evidence.quote.strip()
    if quote:
        if quote not in text:
            return Evidence(kind="missing", reason="引用原文不在指定来源中")
        ev.quote, ev.verification = quote, "quote_verified"
    if step.command:
        command = step.command.strip()
        dependency_file = ev.kind == 'file' and (
            re.search(r'(?:^|/)(?:[\w.-]*requirements[\w.-]*\.(?:txt|in)|requirements/[^/]+\.(?:txt|in))$',
                      ev.source.split('#',1)[0],re.I))
        if dependency_file or is_dependency_declaration(command):
            return Evidence(kind="missing", reason="依赖版本声明不是可执行命令")
        # A tool name inside a dependency/version string is not a command.
        candidates = [source_command_line(line) for line in text.splitlines()]
        inline_commands = re.findall(r"`([^`\n]+)`", text)
        line_match = next((i for i, original in enumerate(candidates)
            if command == original or command == without_shell_comment(original)), None)
        inline_match = next((original for original in inline_commands
            if command == original or command == without_shell_comment(original)), None)
        if line_match is None and inline_match is None:
            return Evidence(kind="missing", reason="指定来源未包含该命令")
        original = candidates[line_match] if line_match is not None else inline_match
        if ev.kind == "file":
            relative_line = line_match + 1 if line_match is not None else text[:text.find(f"`{inline_match}`")].count("\n") + 1
            ev.line_start = (ev.line_start or 1) + relative_line - 1
            ev.line_end = ev.line_start
        ev.quote, ev.verification = original, "command_verified"
    if ev.kind == "file" and ev.quote and ev.line_start is None:
        full = next(d.text for d in sig.doc_files if d.path == ev.source.split("#", 1)[0])
        pos = full.find(ev.quote)
        ev.line_start = full[:pos].count("\n") + 1
        ev.line_end = ev.line_start + ev.quote.count("\n")
    ev.reason = "原文匹配不等于命令已运行或建议语义正确"
    return ev
