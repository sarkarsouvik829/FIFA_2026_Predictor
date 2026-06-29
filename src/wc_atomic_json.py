"""Atomic JSON file writes with retries (Windows / OneDrive file locks)."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any


def write_atomic_json(path: Path, payload: Any, *, indent: int | None = 0) -> None:
    """Write JSON atomically; retry on PermissionError / OSError from locked targets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, indent=indent, ensure_ascii=False)

    last_err: OSError | None = None
    for attempt in range(16):
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            _replace_with_retry(tmp, path)
            return
        except OSError as exc:
            last_err = exc
            time.sleep(0.06 * (attempt + 1) + random.random() * 0.04)
        finally:
            if tmp.exists() and not path.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    if last_err is not None:
        raise last_err
    raise OSError(f"Failed to write {path}")


def _replace_with_retry(tmp: Path, path: Path) -> None:
    last_err: OSError | None = None
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except OSError as exc:
            last_err = exc
            if path.exists():
                try:
                    os.remove(path)
                    os.replace(tmp, path)
                    return
                except OSError as exc2:
                    last_err = exc2
            time.sleep(0.05 * (attempt + 1) + random.random() * 0.03)
    if last_err is not None:
        raise last_err
