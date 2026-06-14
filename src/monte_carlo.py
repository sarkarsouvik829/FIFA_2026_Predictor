"""Monte Carlo tournament simulation — default 100,000 runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal, cast

import numpy as np
import pandas as pd
from tqdm import tqdm

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.predict_match import MatchPredictor
from src.tournament_simulator import cluster_groups, ko_snapshots_to_reach_flags, load_world_cup_2026_group_fixtures, simulate_tournament


def _empty_counts(all_teams: list[str]) -> dict[str, dict[str, int]]:
    return {
        t: {
            "round_of_16": 0,
            "quarter_final": 0,
            "semi_final": 0,
            "final": 0,
            "champion": 0,
        }
        for t in all_teams
    }


def run_simulations(
    n: int = 100_000,
    seed: int = 42,
    model: str = "xgboost",
    draw_rate: float = 0.22,
    sim_date: str = "2026-06-11",
    matches_csv: Path | None = None,
    show_progress: bool = True,
    workers: int | None = None,
) -> pd.DataFrame:
    """Run ``n`` full tournament simulations (sequential; ``workers`` reserved for future use)."""
    del workers  # XGBoost predict is not safely parallel here; keep API for compatibility.
    fx = load_world_cup_2026_group_fixtures(matches_csv)
    groups = cluster_groups(fx)
    all_teams = sorted({t for g in groups for t in g})

    counts = _empty_counts(all_teams)
    engine = MatchPredictor(model=cast(Literal["xgboost", "logistic"], model))

    def predict_fn(home: str, away: str, date: str, tournament: str, neutral: bool) -> float:
        return engine.team_a_win_probability(home, away, date, tournament, neutral)

    rng = np.random.default_rng(seed)
    it = range(n)
    if show_progress:
        it = tqdm(it, desc="Monte Carlo", unit="sim")
    for _ in it:
        res = simulate_tournament(
            predict_fn, sim_date=sim_date, draw_rate=draw_rate, rng=rng, matches_csv=matches_csv
        )
        flags = ko_snapshots_to_reach_flags(res["ko_snapshots"])
        for t in all_teams:
            f = flags.get(t) or {}
            for k in counts[t]:
                if f.get(k):
                    counts[t][k] += 1

    rows = []
    for t in all_teams:
        c = counts[t]
        rows.append(
            {
                "team": t,
                "round_of_16_probability": c["round_of_16"] / n,
                "quarter_final_probability": c["quarter_final"] / n,
                "semi_final_probability": c["semi_final"] / n,
                "final_probability": c["final"] / n,
                "champion_probability": c["champion"] / n,
            }
        )
    return pd.DataFrame(rows).sort_values("champion_probability", ascending=False).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--runs", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=("xgboost", "logistic"), default="xgboost")
    parser.add_argument("-o", "--output", type=Path, default=_ROOT / "outputs" / "monte_carlo_results.csv")
    parser.add_argument("--quick", action="store_true", help="1000 runs for testing")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Ignored (reserved); Monte Carlo runs sequentially for thread safety.",
    )
    args = parser.parse_args()
    n = 1000 if args.quick else args.runs

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df = run_simulations(
        n=n, seed=args.seed, model=args.model, show_progress=True, workers=args.workers
    )
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} teams to {args.output}", file=sys.stderr)
    print(df.head(10).to_string(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
