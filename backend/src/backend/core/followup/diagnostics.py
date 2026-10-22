"""Local, read-only checks. These are tool guidance, never repository evidence."""
from __future__ import annotations

import re


def diagnostic_plan(log_text: str) -> tuple[str, list[str], list[dict[str, str]]]:
    low = log_text.lower()
    hints, checks = [], []
    category = "unknown"

    def check(label: str, command: str, expected: str):
        checks.append({"label": label, "command": command, "expected": expected})

    # Do not match "connection" in a test name such as connection_pool_for_tls.
    # Local CA paths and trust errors have different recovery paths from timeouts.
    missing_ca = "could not find a suitable tls ca certificate bundle" in low
    missing_file = missing_ca or "filenotfounderror" in low or "no such file or directory" in low
    if missing_file:
        category = "local_certificate_path" if missing_ca else "missing_file"
        hints.append("本地证书路径无效：先核对工作目录、文件和父目录是否存在；Windows 还需核对 Git 符号链接是否被检出为普通文本。路径错误尚不能证明证书不受信任或依赖源超时。" if missing_ca else "本地文件缺失：先核对工作目录、当前提交和输入路径，不要先重装依赖。")
        check("确认解释器和工作目录", 'python -c "import sys; from pathlib import Path; print(sys.executable); print(Path.cwd())"', "目录应与当前步骤要求一致；解释器应来自你选择的开发环境。")
        match = re.search(r"invalid path:\s*([^\r\n]+)", log_text, re.I)
        path = match.group(1).strip() if match else ""
        # Only conservative repository-relative literals may enter a shell command.
        if re.fullmatch(r"[A-Za-z0-9_.\-/]+", path) and not path.startswith(("/", "-")) and ".." not in path.split("/"):
            check("检查错误中的文件及各级父目录", f'''python -c "from pathlib import Path; p=Path('{path}'); print([(str(q), q.exists(), q.is_file(), q.is_dir(), q.is_symlink()) for q in [p, *p.parents]])"''', "每行依次是路径、存在、文件、目录、符号链接。若中间父目录是普通文件，先查 Git 的链接记录；尚不能据此确认修复方案。")
            parent = path.rsplit("/", 1)[0] if "/" in path else path
            check("只读核对 Git 文件模式", f"git ls-files -s -- {parent}", "模式 120000 表示仓库中的符号链接；结合上面的本机结果核对。模式 100644/100755 是普通文件。若 Git 记录为链接而本机父目录是文本文件，先保留当前改动，再在支持符号链接的环境（如 Linux/WSL）按同一提交重新准备开发环境，并重跑原测试。不要通过关闭证书校验或排除失败项宣称通过。")
    elif any(s in low for s in ("certificate_verify_failed", "certificate verify failed", "tlsv1_alert_unknown_ca", "tlsv1 alert unknown ca")):
        category = "certificate_trust"
        hints.append("TLS 信任校验失败：先区分远程服务证书、本地 CA 配置及测试生成的证书，并核对报错端点和仓库测试说明；不要关闭证书校验来掩盖错误。")

    if "module not found" in low or "modulenotfounderror" in low:
        category = category if category != "unknown" else "python_environment"
        hints.append("可能缺少依赖或使用了错误环境。核对当前解释器与仓库开发依赖说明，不要直接安装报错中看起来同名的包。")
        check("确认 Python 与 pip 属于同一环境", 'python -c "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"', "venv 中 prefix 与 base_prefix 应不同；继续用此解释器的 python -m pip 核对安装。")
    if "permission denied" in low or "eacces" in low:
        hints.append("可能权限不足：检查目标目录和当前账户权限，先确认仓库推荐的安装方式。")
    if "command not found" in low or "不是内部或外部命令" in log_text or "is not recognized as" in low:
        hints.append("命令未找到：核对所需工具及当前终端的 PATH，安装后可能需要重开终端；先确认仓库要求的版本。")
    network_error = re.search(r"(?:readtimeout|connecttimeout|connectionerror|proxyerror|remotedisconnected)\s*[:(]|\btimed out\b|\bconnection (?:refused|reset|aborted)\b", low)
    if network_error:
        category = category if category != "unknown" else "network"
        hints.append("另有网络异常：" + "先区分依赖下载和测试访问的端点，核对本机代理、DNS、连接及超时条件。只有确认依赖下载源不可达时才考虑更换受信任源；测试网络失败不能由换源直接解决。")
    if "syntaxerror" in low or "indentationerror" in low:
        hints.append("语法/缩进错误：查看异常给出的文件和行号，对照刚改动的代码。")
    if "assertionerror" in low:
        hints.append("测试断言失败：记录具体用例、预期值和实际值，先区分环境差异与代码变更。")
    if not hints:
        hints.append("尚未识别具体异常。请提供第一处异常类型及消息、实际命令、操作系统和退出码；只粘贴脱敏的最小片段。")
    return category, hints, checks
