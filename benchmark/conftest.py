"""Make benchmark tests runnable from the repository root.

The Python project lives in ``backend/``, while the benchmark package is a
top-level sibling.  ``uv run --project backend pytest benchmark/tests`` uses
the backend environment but does not always add the repository root to
``sys.path``.  Keep the test entry point hermetic by adding both source roots
explicitly during pytest collection.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = ROOT / "backend" / "src"

for path in (ROOT, BACKEND_SRC):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
