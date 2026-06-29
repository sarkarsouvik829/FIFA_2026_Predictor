"""Lightweight on-disk usage: session visit counts + prediction run history (JSONL).

Files under data/:

- wc_site_visits.json — {"visits": N}, incremented once per Streamlit browser session.
- wc_prediction_log.jsonl — one JSON object per successful model run.

visitor is a short SHA-256 prefix of the Streamlit session id (opaque, not PII).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any

from src.wc_atomic_json import write_atomic_json

_VISITS_NAME = "wc_site_visits.json"
_LOG_NAME = "wc_prediction_log.jsonl"


def visits_path(root: Path) -> Path:
    return root / "data" / _VISITS_NAME


def prediction_log_path(root: Path) -> Path:
    return root / "data" / _LOG_NAME


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    write_atomic_json(path, payload, indent=0)


def read_visit_count(root: Path) -> int:
    """Return persisted visit total (0 if missing)."""
    p = visits_path(root)
    if not p.is_file():
        return 0
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return 0
    try:
        return int(data.get("visits", 0))
    except (TypeError, ValueError):
        return 0


def increment_visit_count(root: Path) -> int:
    """Increment global visit counter (best-effort under concurrent writes). Returns new total."""
    p = visits_path(root)
    last = 0
    for attempt in range(16):
        cur = read_visit_count(root)
        nxt = cur + 1
        try:
            _write_atomic_json(p, {"version": 1, "visits": nxt})
            return nxt
        except OSError:
            time.sleep(0.025 * (attempt + 1) + random.random() * 0.02)
            last = nxt
    return last or read_visit_count(root)


def visitor_token(session_id: str | None) -> str:
    """Short opaque id for logs (not personally identifying)."""
    if not session_id:
        return "anon"
    h = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return h[:16]


def append_prediction_event(
    root: Path,
    *,
    visitor: str,
    source: str,
    fixture_idx: int,
    home: str,
    away: str,
    model: str,
    res: dict[str, Any],
) -> None:
    """Append one JSON line when a model prediction is stored (skipped on error payloads)."""
    if "_err" in res:
        return
    line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "visitor": visitor,
        "source": source,
        "fixture_idx": fixture_idx,
        "home": home,
        "away": away,
        "model": model,
        "team_a": res.get("team_a"),
        "team_b": res.get("team_b"),
        "team_a_win_probability": res.get("team_a_win_probability"),
        "team_a_expected_goals": res.get("team_a_expected_goals"),
        "team_b_expected_goals": res.get("team_b_expected_goals"),
    }
    path = prediction_log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(line, ensure_ascii=False) + "\n"
    for attempt in range(8):
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            return
        except OSError:
            time.sleep(0.02 * (attempt + 1) + random.random() * 0.01)
