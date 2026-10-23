"""Static command boundaries and working directories; never executes shell text."""
from pathlib import PurePosixPath
import json
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


def source_command_line(line: str) -> str:
    line = re.sub(r'^(?:\$|>)\s*', '', line.strip())
    return re.sub(r'^-?\s*run:\s*', '', line)


def without_shell_comment(command: str) -> str:
    """Remove only a whitespace-delimited # outside quotes; preserve arguments."""
    quote, escaped = '', False
    for i, char in enumerate(command):
        if escaped:
            escaped = False
            continue
        if char in {'\\', '`'} and quote != "'":
            escaped = True
        elif char in {'"', "'"}:
            if not quote: quote = char
            elif quote == char: quote = ''
        elif char == '#' and not quote and (i == 0 or command[i - 1].isspace()):
            return command[:i].rstrip()
    return command.strip()


def command_from_line(line: str) -> str:
    return without_shell_comment(source_command_line(line))


def command_family(command: str) -> str:
    if re.match(r'^(?:npm|pnpm|yarn|corepack)(?=\s|$)',command): return 'javascript'
    if re.match(r'^(?:python\d?|pip\d?|uv|pytest|tox|nox|poetry|conda|virtualenv)(?=\s|$)',command): return 'python'
    return command.split()[0] if command.split() else ''


def input_paths(command: str) -> list[tuple[str, bool]]:
    try:
        args = [a.strip('"\'').replace('\\', '/') for a in shlex.split(without_shell_comment(command), posix=False)]
    except ValueError:
        return []
    result = []
    pip_install = 'pip' in args and 'install' in args or bool(args and args[0] in {'pip', 'pip3'} and 'install' in args)
    for i, arg in enumerate(args):
        if (arg == '--with-requirements' or pip_install and arg in {'-r','--requirement','-c','--constraint'}
                or 'pytest' in args and arg == '-c') and i + 1 < len(args):
            result.append((args[i + 1], False))
        elif arg.startswith(('--requirement=', '--constraint=', '--with-requirements=')):
            result.append((arg.split('=', 1)[1], False))
        elif pip_install and arg.startswith(('-r', '-c')) and not arg.startswith('--') and len(arg) > 2:
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
    if re.search(r'(?:^|\s)(?:--(?:directory|project|dir|cwd|prefix|filter)(?:=|\s)|-C(?:\s|$))', without_shell_comment(command)):
        return None
    doc = next((d for d in sig.doc_files if d.path == source.split('#', 1)[0]), None)
    if not doc:
        return None
    lines = doc.text.splitlines()
    target = line_number - 1 if line_number else next((i for i, line in enumerate(lines)
        if command in {source_command_line(line), command_from_line(line)}), -1)
    if target < 0 or target >= len(lines):
        return None
    if command not in {source_command_line(lines[target]), command_from_line(lines[target])}:
        return None
    start, end, fence = None, None, None
    for i, line in enumerate(lines):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if not match:
            continue
        marker = match[1][0]
        if fence is None:
            start, fence = i, match[1]
        elif marker == fence[0] and len(match[1]) >= len(fence) and not line[match.end():].strip():
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
    for original_line in lines[start + 1:target]:
        line = command_from_line(original_line)
        match = re.match(r'^\s*(?:cd|Set-Location)\s+(?:-Path\s+|-LiteralPath\s+)?(.+?)\s*$', line, re.I)
        if match:
            had_change = True
            value = match[1].strip('"\'').replace('\\', '/')
            if not _relative(value) or re.search(r'[;&|`]', value):
                return None
            # A relative cd is rooted only when its destination is unambiguous.
            if cwd is None:
                doc_directory = PurePosixPath(doc.path).parent
                local_destination = str(doc_directory / value)
                if local_destination in directories:
                    destination = local_destination
                elif value == str(doc_directory) and value in directories:
                    # backend/README's "cd backend" names its own project
                    # entry from repo root, not backend/src/backend's package.
                    destination = value
                else:
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
    script = re.match(r'^(?:npm (?:run )?|pnpm (?:run )?|yarn (?:run )?)(build|test)(?=\s|$)',without_shell_comment(command))
    if script and PurePosixPath(doc.path).stem.lower() == 'readme':
        manifest_path = str(PurePosixPath(doc.path).parent / 'package.json')
        manifest = next((d for d in sig.doc_files if d.path == manifest_path),None)
        if manifest:
            try: data = json.loads(manifest.text)
            except (ValueError,TypeError): data = None
            scripts = data.get('scripts') if isinstance(data,dict) else None
            if isinstance(scripts,dict) and isinstance(scripts.get(script[1]),str) and scripts[script[1]].strip():
                return str(PurePosixPath(doc.path).parent), f'由同目录的 {manifest_path} 中已声明的 {script[1]} 脚本与原文命令共同推导；请核对当前终端位置。'
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
