"""Build training_dataset.csv from Dataset A + historical Elo (decisive matches only)."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.elo_features import HistoricalElo
from src.feature_engineering import FEATURE_COLUMNS, build_feature_row
from src.form_features import MatchFormIndex
from src.matches_common import load_completed_matches_chronological


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matches",
        type=Path,
        default=_ROOT / "data" / "dataset_A_international_matches.csv",
    )
    parser.add_argument(
        "--elo",
        type=Path,
        default=_ROOT / "data" / "dataset_B_historical_elo.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_ROOT / "data" / "training_dataset.csv",
    )
    args = parser.parse_args()

    matches = load_completed_matches_chronological(args.matches)
    elo = HistoricalElo(args.elo)
    form = MatchFormIndex(matches)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = FEATURE_COLUMNS + ["target", "home_goals", "away_goals", "match_id", "date", "home_team", "away_team"]
    n = 0
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for m in matches:
            mid = m["match_id"]
            hs, asc = m["home_score"], m["away_score"]
            if hs == asc:
                continue
            team_a, team_b = m["home_team"], m["away_team"]
            feats = build_feature_row(
                elo,
                form,
                team_a,
                team_b,
                mid,
                m["date"],
                m["tournament"],
                bool(m["neutral"]),
            )
            row = {
                **feats,
                "target": 1 if hs > asc else 0,
                "home_goals": int(hs),
                "away_goals": int(asc),
                "match_id": mid,
                "date": m["date"],
                "home_team": team_a,
                "away_team": team_b,
            }
            w.writerow(row)
            n += 1

    print(f"Wrote {n} training rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
