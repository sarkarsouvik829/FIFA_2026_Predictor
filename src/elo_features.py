"""Elo-based features and historical Elo lookup (no leakage: match_id ordering)."""

from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from pathlib import Path
from typing import Any

INITIAL_ELO = 1500.0


def parse_iso(d: str) -> date:
    return date.fromisoformat(d.strip())


class HistoricalElo:
    """Loads dataset_B_historical_elo.csv; supports queries before a given match_id."""

    def __init__(self, path: Path | str | None = None) -> None:
        root = Path(__file__).resolve().parent.parent
        p = Path(path) if path else root / "data" / "dataset_B_historical_elo.csv"
        self._by_team: dict[str, list[dict[str, Any]]] = {}
        self._elo_before_map: dict[tuple[str, int], float] = {}
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                team = row["team"]
                mid = int(row["match_id"])
                rec = {
                    "match_id": mid,
                    "date": row["date"],
                    "elo_before": float(row["elo_before"]),
                    "elo_after": float(row["elo_after"]),
                }
                self._by_team.setdefault(team, []).append(rec)
                self._elo_before_map[(team, mid)] = float(row["elo_before"])
        for team in self._by_team:
            self._by_team[team].sort(key=lambda r: r["match_id"])
        # Per-team parallel arrays (sorted by match_id) for fast calendar lookup
        self._team_vectors: dict[str, tuple[list[int], list[int], list[float]]] = {}
        for team, arr in self._by_team.items():
            mids = [r["match_id"] for r in arr]
            ords = [parse_iso(r["date"]).toordinal() for r in arr]
            eloa = [float(r["elo_after"]) for r in arr]
            self._team_vectors[team] = (mids, ords, eloa)

    def elo_before_match(self, team: str, match_id: int) -> float:
        return self._elo_before_map.get((team, match_id), INITIAL_ELO)

    def elo_after_last_before(self, team: str, before_match_id: int) -> float:
        """Elo entering match before_match_id (same as elo_before_match at that id)."""
        return self.elo_before_match(team, before_match_id)

    def elo_at_or_before_calendar(
        self, team: str, before_match_id: int, match_date: str, days_ago: int
    ) -> float:
        vec = self._team_vectors.get(team)
        if not vec:
            return INITIAL_ELO
        mids, ords, eloa = vec
        cutoff_ord = parse_iso(match_date).toordinal() - days_ago
        idx = bisect_left(mids, before_match_id)
        if idx == 0:
            return INITIAL_ELO
        sub = ords[:idx]
        j = bisect_right(sub, cutoff_ord) - 1
        if j < 0:
            return INITIAL_ELO
        return eloa[j]

    def peak_elo_in_prior_years(self, team: str, before_match_id: int, match_date: str, years: int = 2) -> float:
        vec = self._team_vectors.get(team)
        if not vec:
            return INITIAL_ELO
        mids, ords, eloa = vec
        start_ord = parse_iso(match_date).toordinal() - 365 * years
        idx = bisect_left(mids, before_match_id)
        peak = INITIAL_ELO
        for j in range(idx - 1, -1, -1):
            if ords[j] < start_ord:
                break
            if eloa[j] > peak:
                peak = eloa[j]
        return peak

    def opponent_elo_before_match(self, opponent: str, match_id: int) -> float:
        return self.elo_before_match(opponent, match_id)


def elo_feature_diffs(
    elo: HistoricalElo,
    team_a: str,
    team_b: str,
    match_id: int,
    match_date: str,
) -> dict[str, float]:
    """Difference features (A - B) for Elo group."""
    a_now = elo.elo_after_last_before(team_a, match_id)
    b_now = elo.elo_after_last_before(team_b, match_id)
    a90 = elo.elo_at_or_before_calendar(team_a, match_id, match_date, 90)
    b90 = elo.elo_at_or_before_calendar(team_b, match_id, match_date, 90)
    a365 = elo.elo_at_or_before_calendar(team_a, match_id, match_date, 365)
    b365 = elo.elo_at_or_before_calendar(team_b, match_id, match_date, 365)
    a_peak = elo.peak_elo_in_prior_years(team_a, match_id, match_date, 2)
    b_peak = elo.peak_elo_in_prior_years(team_b, match_id, match_date, 2)

    return {
        "elo_diff": a_now - b_now,
        "elo_trend_90_diff": (a_now - a90) - (b_now - b90),
        "elo_trend_365_diff": (a_now - a365) - (b_now - b365),
        "peak_elo_2y_diff": a_peak - b_peak,
    }
