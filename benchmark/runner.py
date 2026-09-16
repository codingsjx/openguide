"""Main evaluation runner: orchestrates L1-L4 against golden repos.

Run all:  uv run python -m benchmark.runner
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(mod: str) -> int:
    print(f"\n{'='*70}\n>>> {mod}\n{'='*70}")
    return subprocess.call([sys.executable, "-m", mod])


def main() -> int:
    # L2-L4 live in <pkg>/runner.py; their package __init__ is empty, so the
    # bare package name would silently run nothing.
    codes = [
        _run("benchmark.l1_smoke"),
        _run("benchmark.l2_golden.runner"),
        _run("benchmark.l3_ablation.runner"),
        _run("benchmark.l4_contribution.runner"),
    ]
    failed = sum(1 for c in codes if c != 0)
    print(f"\n评测完成：4 模块中 {failed} 个未通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
