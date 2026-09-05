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


def load_records() -> list[dict]:
    if not _CONTRIB.exists():
        return []
    try:
        return json.loads(_CONTRIB.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


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
    records = load_records()
    print(f"L4 真实贡献记录: {len(records)} 条")
    if not records:
        print("（M5 填入真实 PR/commit 后此处有据）")
        return 1
    for r in records:
        print(f"- [{r['kind']}] {r['owner']}/{r['repo']}  {r['url']}  ({r['note']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
