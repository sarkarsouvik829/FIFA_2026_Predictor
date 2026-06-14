"""Recent form and goal features from match history (strictly before match_id)."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from typing import Any


def _build_team_timeline(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in matches:
        mid = m["match_id"]
        h, a = m["home_team"], m["away_team"]
        hs, asc = m["home_score"], m["away_score"]
        if hs > asc:
            ph, pa = 1.0, 0.0
        elif hs < asc:
            ph, pa = 0.0, 1.0
        else:
            ph, pa = 0.5, 0.5
        by_team[h].append(
            {
                "match_id": mid,
                "gf": hs,
                "ga": asc,
                "opp": a,
                "points": ph,
            }
        )
        by_team[a].append(
            {
                "match_id": mid,
                "gf": asc,
                "ga": hs,
                "opp": h,
                "points": pa,
            }
        )
    for t in by_team:
        by_team[t].sort(key=lambda r: r["match_id"])
    return by_team


class MatchFormIndex:
    def __init__(self, matches: list[dict[str, Any]]) -> None:
        self._by_team = _build_team_timeline(matches)

    def _last_k(self, team: str, before_match_id: int, k: int) -> list[dict[str, Any]]:
        arr = self._by_team.get(team, [])
        if not arr:
            return []
        mids = [r["match_id"] for r in arr]
        i = bisect_left(mids, before_match_id)
        start = max(0, i - k)
        return arr[start:i]

    def win_pct(self, team: str, before_match_id: int, n: int) -> float:
        rows = self._last_k(team, before_match_id, n)
        if not rows:
            return 0.0
        # win = 1, draw = 0.5 for pct numerator same as points/len if we count win as 1 only?
        # Plan: win percentage — typically wins / games (draws not wins). Use wins/n.
        wins = sum(1 for r in rows if r["points"] == 1.0)
        return wins / len(rows)

    def goal_diff_sum(self, team: str, before_match_id: int, n: int) -> float:
        rows = self._last_k(team, before_match_id, n)
        return sum(float(r["gf"] - r["ga"]) for r in rows)

    def goals_scored_rate(self, team: str, before_match_id: int, n: int = 20) -> float:
        rows = self._last_k(team, before_match_id, n)
        if not rows:
            return 0.0
        return sum(r["gf"] for r in rows) / len(rows)

    def goals_conceded_rate(self, team: str, before_match_id: int, n: int = 20) -> float:
        rows = self._last_k(team, before_match_id, n)
        if not rows:
            return 0.0
        return sum(r["ga"] for r in rows) / len(rows)

    def prior_matches(self, team: str, before_match_id: int, n: int) -> list[dict[str, Any]]:
        return self._last_k(team, before_match_id, n)


def form_goal_diffs(form: MatchFormIndex, team_a: str, team_b: str, match_id: int) -> dict[str, float]:
    return {
        "win_pct_5_diff": form.win_pct(team_a, match_id, 5) - form.win_pct(team_b, match_id, 5),
        "win_pct_10_diff": form.win_pct(team_a, match_id, 10) - form.win_pct(team_b, match_id, 10),
        "win_pct_20_diff": form.win_pct(team_a, match_id, 20) - form.win_pct(team_b, match_id, 20),
        "goal_diff_5_diff": form.goal_diff_sum(team_a, match_id, 5) - form.goal_diff_sum(team_b, match_id, 5),
        "goal_diff_10_diff": form.goal_diff_sum(team_a, match_id, 10) - form.goal_diff_sum(team_b, match_id, 10),
        "goal_diff_20_diff": form.goal_diff_sum(team_a, match_id, 20) - form.goal_diff_sum(team_b, match_id, 20),
        "goals_scored_rate_diff": form.goals_scored_rate(team_a, match_id, 20)
        - form.goals_scored_rate(team_b, match_id, 20),
        "goals_conceded_rate_diff": form.goals_conceded_rate(team_a, match_id, 20)
        - form.goals_conceded_rate(team_b, match_id, 20),
    }
