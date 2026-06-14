"""Orchestrate all feature groups for a single match row."""

from __future__ import annotations

import re
from typing import Any

from src.elo_features import HistoricalElo, elo_feature_diffs
from src.form_features import MatchFormIndex, form_goal_diffs
from src.schedule_strength import schedule_diffs

FEATURE_COLUMNS = [
    "elo_diff",
    "elo_trend_90_diff",
    "elo_trend_365_diff",
    "peak_elo_2y_diff",
    "win_pct_5_diff",
    "win_pct_10_diff",
    "win_pct_20_diff",
    "goal_diff_5_diff",
    "goal_diff_10_diff",
    "goal_diff_20_diff",
    "goals_scored_rate_diff",
    "goals_conceded_rate_diff",
    "sos_10_diff",
    "sos_20_diff",
    "strong_team_win_pct_diff",
    "strong_team_goal_diff",
    "tournament_importance",
    "neutral",
]


def tournament_importance(name: str) -> int:
    t = (name or "").strip()
    if t == "FIFA World Cup":
        return 5
    if re.search(r"(?i)qualification|qualifying|qualifier", t):
        return 3
    if re.search(r"(?i)nations league", t):
        return 2
    if t == "Friendly":
        return 1
    # Continental championships and major cups
    if re.search(
        r"(?i)(euro|european championship|copa américa|copa america|africa cup|asian cup|gold cup|oceania)",
        t,
    ):
        return 4
    return 3  # default competitive


def build_feature_row(
    elo: HistoricalElo,
    form: MatchFormIndex,
    team_a: str,
    team_b: str,
    match_id: int,
    match_date: str,
    tournament: str,
    neutral: bool,
) -> dict[str, Any]:
    feats: dict[str, Any] = {}
    feats.update(elo_feature_diffs(elo, team_a, team_b, match_id, match_date))
    feats.update(form_goal_diffs(form, team_a, team_b, match_id))
    feats.update(schedule_diffs(form, elo, team_a, team_b, match_id))
    feats["tournament_importance"] = float(tournament_importance(tournament))
    feats["neutral"] = 1.0 if neutral else 0.0
    return feats
