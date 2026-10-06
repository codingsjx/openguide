"""TTL-backed cache to dodge GitHub API rate limits and speed up repeat runs.

Stores JSON payloads under a `.cache/` dir. Thread-safe enough for single-process
dev servers via a lock.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

_cache_lock = threading.Lock()
_cache_dir = Path(".cache")

# Only characters that are safe in a filename on every platform we target.
# The previous scheme only replaced "/" and ":", so keys like
# `github::repos/o/r?state=open` kept their "?" — an ILLEGAL filename character
# on Windows. Every write then raised OSError, which `set` swallowed, so the
# whole cache silently did nothing on Windows: every run re-hit the GitHub API
# and burned the rate limit (the cause of mid-run 403s in multi-repo runs).
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_MAX_STEM = 100


def _path(key: str) -> Path:
    safe = _UNSAFE.sub("_", key)
    if len(safe) > _MAX_STEM:
        # Keep the name bounded (Windows path limits) without losing uniqueness.
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        safe = f"{safe[:_MAX_STEM]}_{digest}"
    return _cache_dir / f"{safe}.json"


def get(key: str, ttl_s: int) -> dict | None:
    p = _path(key)
    try:
        with _cache_lock:
            if not p.exists():
                return None
            raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - raw.get("ts", 0) > ttl_s:
        try:
            p.unlink()
        except OSError:
            pass
        return None
    return raw.get("data")


def set(key: str, data: dict) -> None:
    payload = {"ts": time.time(), "data": data}
    try:
        _cache_lock.acquire()
        _cache_dir.mkdir(parents=True, exist_ok=True)
        p = _path(key)
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    finally:
        _cache_lock.release()
