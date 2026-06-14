"""Load trained model(s) and predict P(Team A wins) + optional expected goals for a hypothetical match."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.elo_features import HistoricalElo
from src.feature_engineering import FEATURE_COLUMNS, build_feature_row
from src.form_features import MatchFormIndex
from src.matches_common import load_completed_matches_chronological


def _load_context(
    matches_path: Path | None = None,
    elo_path: Path | None = None,
) -> tuple[list[dict[str, Any]], HistoricalElo, MatchFormIndex, int]:
    mp = matches_path or _ROOT / "data" / "dataset_A_international_matches.csv"
    ep = elo_path or _ROOT / "data" / "dataset_B_historical_elo.csv"
    matches = load_completed_matches_chronological(mp)
    if not matches:
        raise RuntimeError("No completed matches found.")
    next_mid = matches[-1]["match_id"] + 1
    elo = HistoricalElo(ep)
    form = MatchFormIndex(matches)
    return matches, elo, form, next_mid


def _load_goal_regressors() -> tuple[Any | None, Any | None]:
    gh = _ROOT / "models" / "xgboost_goals_home.pkl"
    ga = _ROOT / "models" / "xgboost_goals_away.pkl"
    if gh.is_file() and ga.is_file():
        return joblib.load(gh), joblib.load(ga)
    return None, None


class MatchPredictor:
    """Reusable predictor (loads model + match history once)."""

    def __init__(
        self,
        model: Literal["xgboost", "logistic"] = "xgboost",
        matches_path: Path | None = None,
        elo_path: Path | None = None,
    ) -> None:
        self.model = model
        self._matches, self.elo, self.form, self._next_mid = _load_context(matches_path, elo_path)
        mpath = _ROOT / "models" / ("xgboost_model.pkl" if model == "xgboost" else "logistic_regression.pkl")
        self.clf = joblib.load(mpath)
        self._reg_home, self._reg_away = _load_goal_regressors()

    def _feature_matrix(
        self,
        team_a: str,
        team_b: str,
        match_date: str,
        tournament: str,
        neutral: bool,
    ) -> np.ndarray:
        feats = build_feature_row(
            self.elo, self.form, team_a, team_b, self._next_mid, match_date, tournament, neutral
        )
        x = np.array([[feats[c] for c in FEATURE_COLUMNS]], dtype=np.float64)
        return np.nan_to_num(x, posinf=0.0, neginf=0.0)

    def team_a_win_probability(
        self,
        team_a: str,
        team_b: str,
        match_date: str,
        tournament: str = "Friendly",
        neutral: bool = True,
    ) -> float:
        x = self._feature_matrix(team_a, team_b, match_date, tournament, neutral)
        return float(self.clf.predict_proba(x)[0, 1])

    def expected_goals(
        self,
        team_a: str,
        team_b: str,
        match_date: str,
        tournament: str = "Friendly",
        neutral: bool = True,
    ) -> tuple[int | None, int | None]:
        """Expected goals (integer part of regression output) for team_a / team_b, if models exist."""
        if self._reg_home is None or self._reg_away is None:
            return None, None
        x = self._feature_matrix(team_a, team_b, match_date, tournament, neutral)
        eh = max(0.0, float(self._reg_home.predict(x)[0]))
        ea = max(0.0, float(self._reg_away.predict(x)[0]))
        return int(eh), int(ea)

    def reasoning(
        self,
        team_a: str,
        team_b: str,
        match_date: str,
        tournament: str = "Friendly",
        neutral: bool = True,
    ) -> dict[str, Any]:
        """Return supporting data behind the prediction: Elo, recent form, H2H."""
        mid = self._next_mid

        # ── Elo ratings ───────────────────────────────────────────────────
        # Use calendar-based lookup (same as the feature pipeline) so we get
        # the team's latest available Elo rather than INITIAL_ELO for a
        # future match_id that has no entry in the Elo map.
        elo_a = self.elo.elo_at_or_before_calendar(team_a, mid, match_date, 0)
        elo_b = self.elo.elo_at_or_before_calendar(team_b, mid, match_date, 0)
        elo_a_90 = self.elo.elo_at_or_before_calendar(team_a, mid, match_date, 90)
        elo_b_90 = self.elo.elo_at_or_before_calendar(team_b, mid, match_date, 90)

        # ── Recent form (last 5 matches) ──────────────────────────────────
        form_a = [
            {"points": r["points"], "gf": r["gf"], "ga": r["ga"], "opp": r["opp"]}
            for r in self.form.prior_matches(team_a, mid, 5)
        ]
        form_b = [
            {"points": r["points"], "gf": r["gf"], "ga": r["ga"], "opp": r["opp"]}
            for r in self.form.prior_matches(team_b, mid, 5)
        ]

        # ── Goal averages (last 10 matches) ───────────────────────────────
        avg_scored_a = round(self.form.goals_scored_rate(team_a, mid, 10), 2)
        avg_conceded_a = round(self.form.goals_conceded_rate(team_a, mid, 10), 2)
        avg_scored_b = round(self.form.goals_scored_rate(team_b, mid, 10), 2)
        avg_conceded_b = round(self.form.goals_conceded_rate(team_b, mid, 10), 2)

        # ── Head-to-head (all historical meetings, most recent last) ──────
        h2h: list[dict[str, Any]] = []
        for m in self._matches:
            ht, at = m["home_team"], m["away_team"]
            if not ({ht, at} == {team_a, team_b}):
                continue
            hs, as_ = int(m["home_score"]), int(m["away_score"])
            if hs > as_:
                winner = "home"
            elif as_ > hs:
                winner = "away"
            else:
                winner = "draw"
            h2h.append(
                {
                    "date": m["date"],
                    "home": ht,
                    "away": at,
                    "home_score": hs,
                    "away_score": as_,
                    "winner": winner,
                }
            )
        h2h = h2h[-6:]  # keep last 6 meetings

        a_wins = sum(
            1 for m in h2h
            if (m["home"] == team_a and m["winner"] == "home")
            or (m["away"] == team_a and m["winner"] == "away")
        )
        b_wins = sum(
            1 for m in h2h
            if (m["home"] == team_b and m["winner"] == "home")
            or (m["away"] == team_b and m["winner"] == "away")
        )
        draws = len(h2h) - a_wins - b_wins

        return {
            "team_a": team_a,
            "team_b": team_b,
            "elo_a": round(elo_a),
            "elo_b": round(elo_b),
            "elo_trend_a_90": round(elo_a - elo_a_90, 1),
            "elo_trend_b_90": round(elo_b - elo_b_90, 1),
            "form_a": form_a,
            "form_b": form_b,
            "avg_scored_a": avg_scored_a,
            "avg_conceded_a": avg_conceded_a,
            "avg_scored_b": avg_scored_b,
            "avg_conceded_b": avg_conceded_b,
            "h2h": h2h,
            "h2h_a_wins": a_wins,
            "h2h_draws": draws,
            "h2h_b_wins": b_wins,
        }


def predict(
    team_a: str,
    team_b: str,
    match_date: str,
    tournament: str = "Friendly",
    neutral: bool = True,
    model: Literal["xgboost", "logistic"] = "xgboost",
    matches_path: Path | None = None,
    elo_path: Path | None = None,
) -> dict[str, Any]:
    """
    team_a / team_b: exact names as in Dataset A.
    Uses virtual match_id = max historical match_id + 1 so all features use prior history only.

    Win probabilities use ``model`` (xgboost or logistic). Expected goals use the XGBoost goal
    regressors when present; values are the **integer part** (truncated toward zero) of the
    regression output for display.
    """
    eng = MatchPredictor(model=model, matches_path=matches_path, elo_path=elo_path)
    p_a = eng.team_a_win_probability(team_a, team_b, match_date, tournament, neutral)
    eg_a, eg_b = eng.expected_goals(team_a, team_b, match_date, tournament, neutral)
    out: dict[str, Any] = {
        "team_a": team_a,
        "team_b": team_b,
        "team_a_win_probability": round(p_a, 4),
        "team_b_win_probability": round(1.0 - p_a, 4),
    }
    if eg_a is not None and eg_b is not None:
        out["team_a_expected_goals"] = eg_a
        out["team_b_expected_goals"] = eg_b
    return out


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python -m src.predict_match <team_a> <team_b> <date> [tournament] [neutral 0|1]",
            file=sys.stderr,
        )
        sys.exit(1)
    ta, tb, dt = sys.argv[1], sys.argv[2], sys.argv[3]
    tourn = sys.argv[4] if len(sys.argv) > 4 else "Friendly"
    neu = len(sys.argv) > 5 and sys.argv[5] == "1"
    print(json.dumps(predict(ta, tb, dt, tourn, neu)))
