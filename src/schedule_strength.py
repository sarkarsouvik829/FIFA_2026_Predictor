"""Strength-of-schedule features using opponent Elo at match time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.elo_features import HistoricalElo
    from src.form_features import MatchFormIndex

STRONG_ELO = 1800.0


def _sos(form: "MatchFormIndex", elo: "HistoricalElo", team: str, before_match_id: int, n: int) -> float:
    rows = form.prior_matches(team, before_match_id, n)
    if not rows:
        return 0.0
    return sum(elo.opponent_elo_before_match(r["opp"], r["match_id"]) for r in rows) / len(rows)


def _strong_team_stats(form: "MatchFormIndex", elo: "HistoricalElo", team: str, before_match_id: int) -> tuple[float, float]:
    rows = form.prior_matches(team, before_match_id, 20)
    wins, n, gd_sum = 0, 0, 0.0
    for r in rows:
        oelo = elo.opponent_elo_before_match(r["opp"], r["match_id"])
        if oelo <= STRONG_ELO:
            continue
        n += 1
        gd_sum += float(r["gf"] - r["ga"])
        if r["points"] == 1.0:
            wins += 1
    wp = wins / n if n else 0.0
    gd = gd_sum / n if n else 0.0
    return wp, gd


def schedule_diffs(
    form: "MatchFormIndex",
    elo: "HistoricalElo",
    team_a: str,
    team_b: str,
    match_id: int,
) -> dict[str, float]:
    a_wp, a_gd = _strong_team_stats(form, elo, team_a, match_id)
    b_wp, b_gd = _strong_team_stats(form, elo, team_b, match_id)
    return {
        "sos_10_diff": _sos(form, elo, team_a, match_id, 10) - _sos(form, elo, team_b, match_id, 10),
        "sos_20_diff": _sos(form, elo, team_a, match_id, 20) - _sos(form, elo, team_b, match_id, 20),
        "strong_team_win_pct_diff": a_wp - b_wp,
        "strong_team_goal_diff": a_gd - b_gd,
    }
