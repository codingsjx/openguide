"""Static command boundaries and working directories; never executes shell text."""
from pathlib import PurePosixPath
import re
import shlex


_UV_OPTIONS = r"(?:(?:--(?:python|with-requirements|with|group|project|directory)\s+\S+|--(?:frozen|locked|no-sync))\s+)*"
STAGE_COMMAND_PATTERNS = {
    'A': r'^(?:git clone|pip(?:3)? install|uv (?:sync|venv|pip install)|poetry (?:install|sync)|conda (?:create|env create|install)|python(?:3)? -m (?:pip install|venv)|virtualenv|corepack enable|npm (?:ci|install)|pnpm install|yarn(?: install)?|cargo build|go mod (?:download|tidy)|bundle install|gem install|composer install)(?=\s|$)',
    'B': r'^(?:pytest|tox|nox|python(?:3)? -m (?:pytest|unittest)|uv run\s+' + _UV_OPTIONS + r'(?:pytest|python(?:3)? -m (?:pytest|unittest))|npm (?:test|run (?:test|build))|pnpm (?:test|run test|build|run build)|yarn (?:test|run test|build)|cargo test|go test|make (?:test|check)|bundle exec rspec)(?=\s|$)',
    'C': r'^(?:gh issue|git (?:log|branch))(?=\s|$)',
    'D': r'^(?:git (?:checkout|switch|add|commit|push|clone|remote|branch)|gh (?:pr|repo|fork))(?=\s|$)',
}


def is_dependency_declaration(text: str) -> bool:
    # Reject the *whole* declaration too, not just a shortened tool name.
    return bool(re.match(r'^[A-Za-z][\w.-]*(?:\[[^\]]+\])?\s*(?:===|==|!=|~=|>=|<=|>|<)', text.strip()))


def input_paths(command: str) -> list[tuple[str, bool]]:
    try:
        args = [a.strip('"\'').replace('\\', '/') for a in shlex.split(command, posix=False)]
    except ValueError:
        return []
    result = []
    for i, arg in enumerate(args):
        if arg in {'-r', '--requirement', '-c', '--constraint', '--with-requirements'} and i + 1 < len(args):
            result.append((args[i + 1], False))
        elif arg.startswith(('--requirement=', '--constraint=', '--with-requirements=')):
            result.append((arg.split('=', 1)[1], False))
        elif arg.startswith(('-r', '-c')) and not arg.startswith('--') and len(arg) > 2:
            result.append((arg[2:], False))
    if 'pytest' in args or 'unittest' in args:
        result.extend((arg.split('::', 1)[0], not arg.split('::', 1)[0].endswith('.py'))
            for arg in args if re.search(r'(?:^|/)tests(?:/|$)', arg) or arg.endswith('.py'))
    return list(dict.fromkeys(result))


def _relative(value: str) -> bool:
    return bool(value and not re.search(r'^[\\/]|^[A-Za-z]:|://|[*?${}]', value)
                and '..' not in PurePosixPath(value).parts)


def document_directory(sig, source: str, command: str, line_number: int | None = None):
    """Resolve only a matching fenced block's literal cd or unique input paths.

    Separate blocks never inherit cwd. Absolute/user-specific cd paths stay
    unknown. Conflicting or unrecognised directory changes prevent inference.
    """
    if re.search(r'(?:^|\s)--(?:directory|project)(?:=|\s)', command):
        return None
    doc = next((d for d in sig.doc_files if d.path == source.split('#', 1)[0]), None)
    if not doc:
        return None
    lines = doc.text.splitlines()
    target = line_number - 1 if line_number else next((i for i, line in enumerate(lines)
        if re.sub(r'^[$>]\s*', '', line.strip()) == command), -1)
    if target < 0 or target >= len(lines):
        return None
    start, end, fence = None, None, None
    for i, line in enumerate(lines):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if not match:
            continue
        marker = match[1][0]
        if fence is None:
            start, fence = i, marker
        elif marker == fence:
            if start < target < i:
                end = i
                break
            start, fence = None, None
    if start is None or end is None:
        return None
    known = set(sig.file_tree) | {d.path for d in sig.doc_files}
    directories = {'.'} | {str(parent) for p in known for parent in PurePosixPath(p).parents}
    cwd = None
    had_change = False
    for line in lines[start + 1:target]:
        match = re.match(r'^\s*(?:cd|Set-Location)\s+(?:-Path\s+|-LiteralPath\s+)?(.+?)\s*$', line, re.I)
        if match:
            had_change = True
            value = match[1].strip('"\'').replace('\\', '/')
            if not _relative(value) or re.search(r'[;&|`]', value):
                return None
            # A relative cd is rooted only when its destination is unambiguous.
            if cwd is None:
                matches = {p for p in directories if p == value or p.endswith('/' + value)}
                if len(matches) != 1:
                    return None
                destination = matches.pop()
            else:
                destination = str(PurePosixPath(cwd) / value)
            if destination not in directories:
                return None
            cwd = destination
        elif re.search(r'\b(?:pushd|popd|Push-Location|Pop-Location|Set-Location|cd)\b', line, re.I):
            return None
    if had_change:
        return cwd, '依据同一代码块中位于该命令之前的目录切换语句；请在新的终端按原文切换目录。'
    # An input file such as backend/requirements.txt anchors a block without
    # claiming that every root README command runs at repository root.
    options = []
    segment_end = next((i for i in range(target + 1, end)
        if re.match(r'^\s*(?:cd|Set-Location|pushd|popd)\b', lines[i], re.I)), end)
    for line in lines[start + 1:segment_end]:
        if re.match(r'^\s*(?:cd|Set-Location|pushd|popd)\b', line, re.I):
            return None
        for value, allow_directory in input_paths(line.strip()):
            if not _relative(value):
                return None
            matches = {directory for directory in directories
                if str(PurePosixPath(directory) / value) in (directories if allow_directory else known)}
            if matches:
                options.append(matches)
    candidates = set.intersection(*options) if options else set()
    if len(candidates) == 1:
        return candidates.pop(), '由同一代码块中的相对输入路径与已取得文件树匹配推导；仍需核对平台及前置配置。'
    return None
