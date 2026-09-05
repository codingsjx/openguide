"""TTL-backed cache to dodge GitHub API rate limits and speed up repeat runs.

Stores JSON payloads under a `.cache/` dir. Thread-safe enough for single-process
dev servers via a lock.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_cache_lock = threading.Lock()
_cache_dir = Path(".cache")


def _path(key: str) -> Path:
    return _cache_dir / f"{key.replace('/', '__').replace(':', '_')}.json"


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
