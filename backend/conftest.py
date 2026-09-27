import os
import sys
from pathlib import Path

# The importable package is backend/src/backend/ (the tests import
# `from backend.core...`), so the path to add is backend/src — i.e. this
# conftest's own directory plus "src". The previous version climbed one level
# too many and pointed at <repo-root>/src, which does not exist, so plain
# `pytest tests/` failed to import `backend` unless the caller set PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Default tests to the hermetic in-memory index/embedding fallback so they stay
# fast and offline (no chromadb model download). Override with USE_CHROMA=true
# for an integration run.
os.environ.setdefault("USE_CHROMA", "false")
