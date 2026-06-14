"""
FIFA 2026 group stage from Dataset A (72 unplayed group fixtures), then knockout.
Group stage: multinomial over (home win, draw, away win) with configurable draw rate.
Knockout: Bernoulli from model P(home wins) with random side ordering each tie.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MatchPredictFn = Callable[[str, str, str, str, bool], float]


def _parse_na_scores(hs: str, as_: str) -> bool:
    return hs.strip().upper() == "NA" or as_.strip().upper() == "NA"


def load_world_cup_2026_group_fixtures(matches_csv: Path | None = None) -> list[dict[str, Any]]:
    p = matches_csv or _ROOT / "data" / "dataset_A_international_matches.csv"
    out: list[dict[str, Any]] = []
    with p.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("tournament", "").strip() != "FIFA World Cup":
                continue
            if not row["date"].startswith("2026-"):
                continue
            if not _parse_na_scores(row["home_score"], row["away_score"]):
                continue
            out.append(
                {
                    "date": row["date"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "neutral": str(row.get("neutral", "FALSE")).strip().upper() == "TRUE",
                }
            )
    out.sort(key=lambda r: (r["date"], r["home_team"], r["away_team"]))
    return out


def _uf_parent(parent: dict[str, str], x: str) -> str:
    if x not in parent:
        parent[x] = x
    if parent[x] != x:
        parent[x] = _uf_parent(parent, parent[x])
    return parent[x]


def _uf_union(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _uf_parent(parent, a), _uf_parent(parent, b)
    if ra != rb:
        parent[ra] = rb


def cluster_groups(fixtures: list[dict[str, Any]]) -> list[list[str]]:
    """12 groups of 4 from round-robin connectivity."""
    parent: dict[str, str] = {}
    for f in fixtures:
        _uf_union(parent, f["home_team"], f["away_team"])
    buckets: dict[str, list[str]] = defaultdict(list)
    for f in fixtures:
        for t in (f["home_team"], f["away_team"]):
            buckets[_uf_parent(parent, t)].append(t)
    groups = []
    for _, members in buckets.items():
        g = sorted(set(members))
        if len(g) == 4:
            groups.append(g)
    groups.sort(key=lambda g: g[0])
    return groups


def _standings_key(s: dict[str, Any]) -> tuple[int, int, int]:
    return (s["pts"], s["gd"], s["gf"])


def simulate_group_stage(
    groups: list[list[str]],
    fixtures: list[dict[str, Any]],
    predict_win_prob: MatchPredictFn,
    sim_date: str,
    draw_rate: float,
    rng,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Returns (standings per team key, list of third-place summaries sorted for ranking)."""
    # team -> {pts, gf, ga, gd}
    st: dict[str, dict[str, Any]] = {}
    for g in groups:
        for t in g:
            st[t] = {"pts": 0, "gf": 0, "ga": 0, "gd": 0, "group": tuple(g)}

    for fx in fixtures:
        h, a = fx["home_team"], fx["away_team"]
        if h not in st or a not in st:
            continue
        ph_raw = predict_win_prob(h, a, sim_date, "FIFA World Cup", fx["neutral"])
        ph_raw = min(max(ph_raw, 0.02), 0.98)
        d = draw_rate
        rem = 1.0 - d
        p_home = rem * ph_raw
        p_away = rem * (1.0 - ph_raw)
        u = rng.random()
        if u < p_home:
            st[h]["pts"] += 3
            hg = int(rng.integers(1, 4))
            ag = int(rng.integers(0, hg))
            st[h]["gf"] += hg
            st[h]["ga"] += ag
            st[a]["gf"] += ag
            st[a]["ga"] += hg
        elif u < p_home + d:
            st[h]["pts"] += 1
            st[a]["pts"] += 1
            g = int(rng.integers(0, 3))
            st[h]["gf"] += g
            st[a]["gf"] += g
        else:
            st[a]["pts"] += 3
            ag = int(rng.integers(1, 4))
            hg = int(rng.integers(0, ag))
            st[a]["gf"] += ag
            st[a]["ga"] += hg
            st[h]["gf"] += hg
            st[h]["ga"] += ag
        st[h]["gd"] = st[h]["gf"] - st[h]["ga"]
        st[a]["gd"] = st[a]["gf"] - st[a]["ga"]

    # rank within each group
    third_rows: list[dict[str, Any]] = []
    for g in groups:
        ranked = sorted(g, key=lambda t: _standings_key(st[t]), reverse=True)
        for i, t in enumerate(ranked):
            st[t]["group_rank"] = i + 1
        third_rows.append(
            {
                "team": ranked[2],
                "pts": st[ranked[2]]["pts"],
                "gd": st[ranked[2]]["gd"],
                "gf": st[ranked[2]]["gf"],
            }
        )
    return st, third_rows


def select_third_place(third_rows: list[dict[str, Any]], n: int = 8) -> list[str]:
    third_rows = sorted(third_rows, key=lambda r: (r["pts"], r["gd"], r["gf"]), reverse=True)
    return [r["team"] for r in third_rows[:n]]


def build_r32_field(groups: list[list[str]], standings: dict[str, dict[str, Any]], thirds: list[str]) -> list[str]:
    qualifiers: list[str] = []
    for g in groups:
        ranked = sorted(g, key=lambda t: _standings_key(standings[t]), reverse=True)
        qualifiers.append(ranked[0])
        qualifiers.append(ranked[1])
    qualifiers.extend(thirds)
    if len(qualifiers) != 32:
        # Fallback pad (should not happen)
        while len(qualifiers) < 32:
            qualifiers.append(qualifiers[-1])
    return qualifiers[:32]


def simulate_knockout(
    teams: list[str],
    predict_win_prob: MatchPredictFn,
    sim_date: str,
    rng,
) -> tuple[str, list[set[str]]]:
    """
    Single elimination from 32 teams.
    Returns (champion, list_of_sets): sets[k] = teams still alive at start of KO round k
    (k=0 is R32 field, k=1 is R16, ..., last singleton is champion).
    """
    alive = [t for t in teams if t]
    if not alive:
        return "", []
    if len(alive) == 1:
        return alive[0], [{alive[0]}]

    rng.shuffle(alive)
    snapshots: list[set[str]] = [set(alive)]
    while len(alive) > 1:
        if len(alive) % 2 == 1:
            alive.append(alive[-1])
        nxt: list[str] = []
        for i in range(0, len(alive), 2):
            a, b = alive[i], alive[i + 1]
            if a == b:
                nxt.append(a)
                continue
            ph = predict_win_prob(a, b, sim_date, "FIFA World Cup", True)
            ph = min(max(ph, 0.02), 0.98)
            if rng.random() < ph:
                nxt.append(a)
            else:
                nxt.append(b)
        alive = nxt
        snapshots.append(set(alive))
    return alive[0], snapshots


def simulate_tournament(
    predict_win_prob: MatchPredictFn,
    sim_date: str = "2026-06-11",
    draw_rate: float = 0.22,
    rng=None,
    matches_csv: Path | None = None,
) -> dict[str, Any]:
    if rng is None:
        import numpy as np

        rng = np.random.default_rng()
    fixtures = load_world_cup_2026_group_fixtures(matches_csv)
    groups = cluster_groups(fixtures)
    st, thirds_all = simulate_group_stage(groups, fixtures, predict_win_prob, sim_date, draw_rate, rng)
    thirds = select_third_place(thirds_all, 8)
    field = build_r32_field(groups, st, thirds)
    champion, ko_snapshots = simulate_knockout(field, predict_win_prob, sim_date, rng)
    all_teams = sorted({t for g in groups for t in g})
    return {
        "champion": champion,
        "ko_snapshots": ko_snapshots,
        "standings": st,
        "qualifiers_32": field,
        "all_teams": all_teams,
    }


def ko_snapshots_to_reach_flags(snapshots: list[set[str]]) -> dict[str, dict[str, bool]]:
    """snapshots[0]=R32 field; snapshots[1]=R16; ... last = {champion}."""
    out: dict[str, dict[str, bool]] = {}
    if not snapshots:
        return out
    r16 = snapshots[1] if len(snapshots) > 1 else set()
    qf = snapshots[2] if len(snapshots) > 2 else set()
    sf = snapshots[3] if len(snapshots) > 3 else set()
    fin = snapshots[4] if len(snapshots) > 4 else set()
    all_seen = set().union(*snapshots) if snapshots else set()
    for t in all_seen:
        out[t] = {
            "round_of_16": t in r16,
            "quarter_final": t in qf,
            "semi_final": t in sf,
            "final": t in fin,
            "champion": t in snapshots[-1] and len(snapshots[-1]) == 1,
        }
    return out
