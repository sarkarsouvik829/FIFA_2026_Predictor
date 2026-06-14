"""Shared helpers for loading completed international matches in chronological order."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def parse_scores(home_score: str, away_score: str) -> tuple[int, int] | None:
    hs, as_ = home_score.strip(), away_score.strip()
    if hs.upper() == "NA" or as_.upper() == "NA":
        return None
    try:
        return int(hs), int(as_)
    except ValueError:
        return None


def load_completed_matches_chronological(
    path: Path | str,
) -> list[dict[str, Any]]:
    """Return completed matches sorted by (date, original_row_index), each with match_id."""
    p = Path(path)
    raw: list[tuple[dict[str, str], int]] = []
    with p.open(newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            raw.append((row, i))
    raw.sort(key=lambda ri: (ri[0]["date"], ri[1]))

    out: list[dict[str, Any]] = []
    mid = 0
    for row, _ in raw:
        sc = parse_scores(row["home_score"], row["away_score"])
        if sc is None:
            continue
        h, a = sc
        neutral = str(row.get("neutral", "FALSE")).strip().upper() == "TRUE"
        m = {
            "match_id": mid,
            "date": row["date"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": h,
            "away_score": a,
            "tournament": row.get("tournament", ""),
            "neutral": neutral,
        }
        out.append(m)
        mid += 1
    return out
