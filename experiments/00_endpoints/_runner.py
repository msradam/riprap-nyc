"""Tiny harness shared by the 8 smoke tests.

Each test exposes a `probe()` callable that returns (ok, summary, payload).
Cache hits are kept in .cache/ as JSON or raw bytes; tests are idempotent.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)


def cache_path(key: str, ext: str = "json") -> Path:
    return CACHE / f"{key}.{ext}"


def write_cache(key: str, obj, ext: str = "json") -> None:
    p = cache_path(key, ext)
    if ext == "json":
        p.write_text(json.dumps(obj, default=str)[:200_000])
    else:
        p.write_bytes(obj if isinstance(obj, bytes) else str(obj).encode())


def run(name: str, fn) -> tuple[bool, str, float]:
    t0 = time.time()
    try:
        ok, summary, payload = fn()
        dt = time.time() - t0
        return ok, summary, dt
    except Exception as e:
        traceback.print_exc()
        dt = time.time() - t0
        return False, f"exception: {type(e).__name__}: {e}", dt


def cli(name: str, fn) -> int:
    ok, summary, dt = run(name, fn)
    badge = "PASS" if ok else "FAIL"
    print(f"{badge}  {name}  ({dt:.2f}s)  {summary}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(0)
