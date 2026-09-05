"""Repository URL parsing helpers.

Input forms accepted:
- https://github.com/owner/repo
- https://github.com/owner/repo/tree/main (branch path ignored)
- owner/repo  (shorthand)

Raises ValueError on malformed input.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_REPO_SHORTHAND = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def parse_github_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) from a GitHub URL or shorthand."""
    if not url or not isinstance(url, str):
        raise ValueError("仓库 URL 不能为空")
    url = url.strip().rstrip("/")

    if "://" not in url:
        # shorthand "owner/repo"
        if _REPO_SHORTHAND.match(url):
            owner, repo = url.split("/", 1)
            return owner, repo
        raise ValueError(f"无法识别的仓库标识: {url!r}")

    parsed = urlparse(url)
    if parsed.netloc.lower() not in ("github.com", "www.github.com"):
        raise ValueError(f"仅支持 GitHub 仓库，当前: {parsed.netloc!r}")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"无法从 URL 解析出 owner/repo: {url!r}")
    return parts[0], parts[1]
