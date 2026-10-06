"""L4 real-contribution log (skeleton).

Records evidence of the "作品也回馈开源" closure: the real PR/commit we submit
to a small upstream repo using our own guide (方向三佐证). M5 填入真实链接。

Run:  uv run python -m benchmark.l4_contribution
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CONTRIB = ROOT / "l4_contribution" / "records.json"


class RecordsCorrupt(RuntimeError):
    """records.json exists but is not valid JSON (a real error, unlike "empty")."""


def load_records() -> list[dict]:
    """Return the contribution records. Missing file == no records yet (not an error)."""
    if not _CONTRIB.exists():
        return []
    try:
        data = json.loads(_CONTRIB.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecordsCorrupt(f"{_CONTRIB} 不是合法 JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RecordsCorrupt(f"{_CONTRIB} 顶层应为数组，实际是 {type(data).__name__}")
    return data


def add_record(owner: str, repo: str, kind: str, url: str, note: str) -> None:
    """kind: pr | commit | docs | issue 等。M5 调用写入真实记录。"""
    records = load_records()
    records.append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "owner": owner,
            "repo": repo,
            "kind": kind,
            "url": url,
            "note": note,
        }
    )
    _CONTRIB.parent.mkdir(parents=True, exist_ok=True)
    _CONTRIB.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    """L4 状态机。

    - PENDING（退出 0）：尚无记录。这是**待补充状态，不是失败**——本模块是 M5 才
      填真实 PR/commit 的骨架，没有记录时整条评测链不应被判为未通过。
    - OK（退出 0）：有记录，逐条打印。
    - FAIL（退出 1）：记录文件损坏（真错误）。

    口径红线仍然成立：**没有记录就不会被算作"闭环已完成"**——报告里明确标注
    PENDING，评审一眼能看出这一项还缺真实链接，而不是被静默当成通过。
    """
    try:
        records = load_records()
    except RecordsCorrupt as exc:
        print(f"L4 记录文件损坏: {exc}")
        return 1

    print(f"L4 真实贡献记录: {len(records)} 条")
    if not records:
        print("状态: PENDING —— 尚无真实 PR/commit 记录")
        print("（用 add_record(...) 补录后本模块转为 OK；见 benchmark/README.md）")
        return 0

    print("状态: OK")
    for r in records:
        print(f"- [{r['kind']}] {r['owner']}/{r['repo']}  {r['url']}  ({r['note']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
