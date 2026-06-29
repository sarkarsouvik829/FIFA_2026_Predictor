"""Local JSON cache for live FT scores and per-fixture model predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.wc_atomic_json import write_atomic_json

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
    write_atomic_json(path, payload, indent=0)


def merge_save_predictions_batch(
    root: Path,
    items: list[tuple[int, dict[str, Any], dict[str, Any] | None]],
) -> bool:
    """Persist many fixture predictions in one disk write."""
    if not items:
        return True
    cur_l, cur_p, cur_r = load_triple(root)
    for idx, res, reasoning in items:
        if "_err" in res:
            continue
        cur_p[idx] = res
        if reasoning is not None:
            cur_r[idx] = reasoning
    return save_triple(root, cur_l, cur_p, cur_r)


def save_triple(
    root: Path,
    live_ft: dict[int, str],
    predictions: dict[int, dict[str, Any]],
    reasoning: dict[int, Any],
) -> bool:
    """Overwrite cache file with full maps (string JSON keys). Returns False if disk write fails."""
    payload = {
        "version": 1,
        "live_ft": {str(k): v for k, v in live_ft.items()},
        "predictions": {str(k): v for k, v in predictions.items()},
        "reasoning": {str(k): v for k, v in reasoning.items()},
    }
    try:
        _write_atomic(cache_path(root), payload)
        return True
    except OSError:
        return False


def merge_save_live_ft(root: Path, live_by_idx: dict[int, str]) -> bool:
    """Merge ``live_by_idx`` into on-disk ``live_ft`` and save (preserves predictions)."""
    cur_l, cur_p, cur_r = load_triple(root)
    cur_l.update(live_by_idx)
    return save_triple(root, cur_l, cur_p, cur_r)


def merge_save_prediction(root: Path, idx: int, res: dict[str, Any], reasoning: dict[str, Any] | None) -> bool:
    """Store one fixture prediction (+ optional reasoning) and save."""
    if "_err" in res:
        return True
    cur_l, cur_p, cur_r = load_triple(root)
    cur_p[idx] = res
    if reasoning is not None:
        cur_r[idx] = reasoning
    return save_triple(root, cur_l, cur_p, cur_r)
