"""
Compute historical Elo time series from Dataset A (completed matches only).

Writes: data/dataset_B_historical_elo.csv
Columns: match_id, date, team, elo_before, elo_after

K-factor: FIFA World Cup = 40, other competitive = 30, Friendly = 20.
Starting rating: 1500. Home advantage: +60 Elo points to home when not neutral.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.matches_common import load_completed_matches_chronological

INITIAL_ELO = 1500.0
HOME_ADVANTAGE = 60.0


def k_factor(tournament: str) -> float:
    t = (tournament or "").strip()
    if t == "Friendly":
        return 20.0
    if t == "FIFA World Cup":
        return 40.0
    return 30.0


def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (rb - ra) / 400.0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matches",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "dataset_A_international_matches.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "dataset_B_historical_elo.csv",
    )
    args = parser.parse_args()

    rows = load_completed_matches_chronological(args.matches)

    team_elo: dict[str, float] = {}
    out_rows: list[tuple[int, str, str, float, float]] = []
    mid = 0

    for m in rows:
        home, away = m["home_team"], m["away_team"]
        h, a = m["home_score"], m["away_score"]
        neutral = m["neutral"]
        tournament = m["tournament"]
        d = m["date"]

        rh = team_elo.get(home, INITIAL_ELO)
        ra = team_elo.get(away, INITIAL_ELO)
        eff_home = rh + (0.0 if neutral else HOME_ADVANTAGE)
        eh = expected_score(eff_home, ra)
        if h > a:
            sh, sa = 1.0, 0.0
        elif h < a:
            sh, sa = 0.0, 1.0
        else:
            sh, sa = 0.5, 0.5

        k = k_factor(tournament)
        new_h = rh + k * (sh - eh)
        new_a = ra + k * (sa - (1.0 - eh))
        team_elo[home] = new_h
        team_elo[away] = new_a

        out_rows.append((mid, d, home, rh, new_h))
        out_rows.append((mid, d, away, ra, new_a))
        mid += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["match_id", "date", "team", "elo_before", "elo_after"])
        for mid, d, team, elo_b, elo_a in out_rows:
            w.writerow([mid, d, team, f"{elo_b:.4f}", f"{elo_a:.4f}"])

    print(f"Wrote {len(out_rows)} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
