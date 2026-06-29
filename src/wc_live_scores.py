"""Fetch live FIFA World Cup 2026 scores from ESPN's public JSON API.

The same scores appear in Google Search sports widgets and ESPN; we use ESPN
because it returns structured JSON (no HTML scraping of google.com).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# ESPN displayName / shortName quirks → substring match keys after _norm_token
_ALIASES: list[tuple[str, str]] = [
    ("bosniaherzegovina", "Bosnia and Herzegovina"),
    ("ivorycoast", "Ivory Coast"),
    ("czechia", "Czech Republic"),
    ("czechrepublic", "Czech Republic"),
    ("southkorea", "South Korea"),
    ("unitedstates", "United States"),
    ("usa", "United States"),
    ("curacao", "Curaçao"),
    ("curaçao", "Curaçao"),
    ("drcongo", "DR Congo"),
    ("congodr", "DR Congo"),
    ("bosniaherzegovina", "Bosnia and Herzegovina"),
    ("bosnia-herzegovina", "Bosnia and Herzegovina"),
    ("turkey", "Turkey"),
    ("trkiye", "Turkey"),
    ("uae", "United Arab Emirates"),
]


def _norm_team(s: str) -> str:
    """Fold team name to a single comparable token string."""
    t = s.strip().lower()
    t = t.replace("’", "'")
    t = re.sub(r"[^a-z0-9]+", "", t)
    for needle, _ in _ALIASES:
        if needle in t:
            return needle
    return t


def _canonical_fixture_name(name: str) -> str:
    """Map ESPN / alias token back to a string comparable to our _norm_team on fixture names."""
    n = _norm_team(name)
    for needle, canonical in _ALIASES:
        if n == needle or needle in n:
            return _norm_team(canonical)
    return n


def _teams_match(a: str, b: str) -> bool:
    """True if display names refer to the same side (fuzzy)."""
    na, nb = _norm_team(a), _norm_team(b)
    if na == nb:
        return True
    ca, cb = _canonical_fixture_name(a), _canonical_fixture_name(b)
    return ca == cb or na in nb or nb in na or ca in cb or cb in ca


def _parse_event_scores(comp: dict[str, Any]) -> tuple[str, str, int, int] | None:
    """Return (home_name, away_name, home_score, away_score) or None."""
    teams = comp.get("competitors") or []
    if len(teams) != 2:
        return None
    home = away = None
    hs = asc = 0
    for c in teams:
        side = c.get("homeAway")
        name = (c.get("team") or {}).get("displayName") or (c.get("team") or {}).get("shortName") or ""
        try:
            sc = int(c.get("score", "0"))
        except (TypeError, ValueError):
            sc = 0
        if side == "home":
            home, hs = name, sc
        elif side == "away":
            away, asc = name, sc
    if not home or not away:
        return None
    return home, away, hs, asc


def _fetch_scoreboard_json(ymd: str) -> dict[str, Any] | None:
    """ymd = YYYYMMDD. Returns parsed JSON or None on failure."""
    url = f"{ESPN_SCOREBOARD}?dates={ymd}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; FIFA-WC-Predictor/1.0; +https://example.local)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _event_kickoff_date(ev: dict[str, Any]) -> date | None:
    ds = ev.get("date")
    if not ds or not isinstance(ds, str):
        return None
    try:
        return datetime.fromisoformat(ds.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def fetch_live_scores_by_fixture_idx(
    fixtures: list[dict[str, Any]],
    dates_to_query: list[str],
) -> dict[int, str]:
    """
    Match finished ESPN scoreboard events to fixtures by team names.
    Allows ±1 calendar day between our schedule row and ESPN's kickoff date
    (broadcast / timezone skew).
    """
    # Collect completed events: (kickoff_date, home_espn, away_espn, home_score, away_score)
    events: list[tuple[date, str, str, int, int]] = []
    seen_event_ids: set[str] = set()
    for ymd in dates_to_query:
        data = _fetch_scoreboard_json(ymd)
        if not data:
            continue
        for ev in data.get("events") or []:
            eid = str(ev.get("id") or "")
            if eid:
                if eid in seen_event_ids:
                    continue
                seen_event_ids.add(eid)
            comps = ev.get("competitions") or []
            if not comps:
                continue
            comp = comps[0]
            stype = (comp.get("status") or {}).get("type") or {}
            if not stype.get("completed"):
                continue
            parsed = _parse_event_scores(comp)
            if not parsed:
                continue
            eh, ea, sh, sa = parsed
            kd = _event_kickoff_date(ev)
            if kd is None:
                kd = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))
            events.append((kd, eh, ea, sh, sa))

    out: dict[int, str] = {}
    for fx in fixtures:
        idx = fx["_idx"]
        fxd = date.fromisoformat(fx["date"])
        best: tuple[int, str] | None = None  # (day_delta, score_str)
        for kd, eh, ea, sh, sa in events:
            dd = abs((kd - fxd).days)
            if dd > 1:
                continue
            score_h_a = f"{sh} – {sa}"
            score_a_h = f"{sa} – {sh}"
            if _teams_match(eh, fx["home"]) and _teams_match(ea, fx["away"]):
                cand = (dd, score_h_a)
            elif _teams_match(ea, fx["home"]) and _teams_match(eh, fx["away"]):
                cand = (dd, score_a_h)
            else:
                continue
            if best is None or cand[0] < best[0]:
                best = cand
        if best:
            out[idx] = best[1]
    return out


def dates_up_to_today_inclusive(first_iso: str, last_iso: str, today: date) -> list[str]:
    """Return YYYYMMDD strings for every day from max(first,?) through min(last, today)."""
    d0 = date.fromisoformat(first_iso)
    d1 = date.fromisoformat(last_iso)
    end = min(d1, today)
    if end < d0:
        return []
    out: list[str] = []
    cur = d0
    while cur <= end:
        out.append(cur.strftime("%Y%m%d"))
        cur = date.fromordinal(cur.toordinal() + 1)
    return out
