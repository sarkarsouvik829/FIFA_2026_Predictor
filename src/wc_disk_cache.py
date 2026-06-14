"""Local JSON cache for live FT scores and per-fixture model predictions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CACHE_NAME = "wc_app_cache.json"


def cache_path(root: Path) -> Path:
    return root / "data" / _CACHE_NAME


def load_triple(root: Path) -> tuple[dict[int, str], dict[int, dict[str, Any]], dict[int, Any]]:
    """Return (live_ft, predictions, reasoning) with int keys; missing file → empty dicts."""
    p = cache_path(root)
    if not p.is_file():
        return {}, {}, {}
    try:
        with p.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}, {}, {}

    def _int_dict(d: Any) -> dict[int, Any]:
        if not isinstance(d, dict):
            return {}
        out: dict[int, Any] = {}
        for k, v in d.items():
            try:
                out[int(k)] = v
            except (TypeError, ValueError):
                continue
        return out

    return (
        _int_dict(raw.get("live_ft")),
        _int_dict(raw.get("predictions")),
        _int_dict(raw.get("reasoning")),
    )


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=0, ensure_ascii=False)
    os.replace(tmp, path)


def save_triple(
    root: Path,
    live_ft: dict[int, str],
    predictions: dict[int, dict[str, Any]],
    reasoning: dict[int, Any],
) -> None:
    """Overwrite cache file with full maps (string JSON keys)."""
    payload = {
        "version": 1,
        "live_ft": {str(k): v for k, v in live_ft.items()},
        "predictions": {str(k): v for k, v in predictions.items()},
        "reasoning": {str(k): v for k, v in reasoning.items()},
    }
    _write_atomic(cache_path(root), payload)


def merge_save_live_ft(root: Path, live_by_idx: dict[int, str]) -> None:
    """Merge ``live_by_idx`` into on-disk ``live_ft`` and save (preserves predictions)."""
    cur_l, cur_p, cur_r = load_triple(root)
    cur_l.update(live_by_idx)
    save_triple(root, cur_l, cur_p, cur_r)


def merge_save_prediction(root: Path, idx: int, res: dict[str, Any], reasoning: dict[str, Any] | None) -> None:
    """Store one fixture prediction (+ optional reasoning) and save."""
    if "_err" in res:
        return
    cur_l, cur_p, cur_r = load_triple(root)
    cur_p[idx] = res
    if reasoning is not None:
        cur_r[idx] = reasoning
    save_triple(root, cur_l, cur_p, cur_r)
