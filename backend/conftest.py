import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Default tests to the hermetic in-memory index/embedding fallback so they stay
# fast and offline (no chromadb model download). Override with USE_CHROMA=true
# for an integration run.
os.environ.setdefault("USE_CHROMA", "false")
