"""Knockout schedule from ESPN scoreboard with per-round local cache.

ESPN ``season.slug`` is one stage ahead of FIFA naming for placeholder slots
(e.g. slug ``quarterfinals`` holds Round of 16 bracket games). Resolved
fixtures (both sides are real countries) are mapped to our round labels.

Cache: ``data/wc_knockout_schedule.json`` — when a round is marked complete
(all expected matches have real teams), that round is not re-fetched from the web.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.wc_atomic_json import write_atomic_json

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
_CACHE_NAME = "wc_knockout_schedule.json"

# Knockout window (group stage ends ~Jun 27; final Jul 19)
_KO_FIRST = "20260628"
_KO_LAST = "20260719"

KNOCKOUT_ROUNDS_ORDER: list[str] = [
    "Round of 32",
    "Round of 16",
    "Quarter-Finals",
    "Semi-Finals",
    "3rd Place",
    "Final",
]

ROUND_EXPECTED: dict[str, int] = {
    "Round of 32": 16,
    "Round of 16": 8,
    "Quarter-Finals": 4,
    "Semi-Finals": 2,
    "3rd Place": 1,
    "Final": 1,
}

# Rounds the app actively resolves from ESPN (R16 and later; R32 included when available).
ROUNDS_FROM_R16: tuple[str, ...] = (
    "Round of 16",
    "Quarter-Finals",
    "Semi-Finals",
    "3rd Place",
    "Final",
)

_PLACEHOLDER_RE = re.compile(
    r"(round of \d+|quarterfinal|semifinal|\bwinner\b|\bloser\b|\btbd\b|to be determined)",
    re.I,
)

# ESPN displayName → fixture / dataset label used elsewhere in the app
_ESPN_DISPLAY: dict[str, str] = {
    "Congo DR": "DR Congo",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "USA": "United States",
    "Korea Republic": "South Korea",
    "Korea, Republic of": "South Korea",
}


def cache_path(root: Path) -> Path:
    return root / "data" / _CACHE_NAME


def _is_real_team(name: str) -> bool:
    if not name or not name.strip():
        return False
    return _PLACEHOLDER_RE.search(name.strip()) is None


def _norm_display(name: str) -> str:
    n = name.strip()
    return _ESPN_DISPLAY.get(n, n)


def _round_from_slug(slug: str) -> str | None:
    """Map ESPN slug + real teams to our round label."""
    m = {
        "round-of-32": "Round of 32",
        "round-of-16": "Round of 32",  # ESPN: remaining R32 slots
        "quarterfinals": "Round of 16",
        "semifinals": "Quarter-Finals",
        "3rd-place-match": "3rd Place",
        "final": "Final",
    }
    return m.get(slug or "")


def _fetch_scoreboard_range(first_ymd: str, last_ymd: str) -> list[dict[str, Any]]:
    url = f"{ESPN_SCOREBOARD}?dates={first_ymd}-{last_ymd}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; FIFA-WC-Predictor/1.0)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    return list(data.get("events") or [])


def _parse_resolved_event(ev: dict[str, Any]) -> dict[str, Any] | None:
    comps = ev.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    home = away = None
    for c in comp.get("competitors") or []:
        side = c.get("homeAway")
        raw = (c.get("team") or {}).get("displayName") or (c.get("team") or {}).get("shortName") or ""
        if side == "home":
            home = raw
        elif side == "away":
            away = raw
    if not home or not away or not _is_real_team(home) or not _is_real_team(away):
        return None

    slug = (ev.get("season") or {}).get("slug") or ""
    rnd = _round_from_slug(slug)
    if not rnd:
        return None

    ds = ev.get("date") or ""
    try:
        kickoff = datetime.fromisoformat(ds.replace("Z", "+00:00"))
        day = kickoff.date().isoformat()
    except ValueError:
        day = ds[:10] if len(ds) >= 10 else ""

    venue_obj = comp.get("venue") or {}
    venue = venue_obj.get("fullName") or ""
    addr = venue_obj.get("address") or {}
    city = addr.get("city") or ""
    if venue and city and city not in venue:
        venue = f"{venue}, {city}"

    eid = str(ev.get("id") or "")
    hn, an = _norm_display(home), _norm_display(away)
    return {
        "round": rnd,
        "date": day,
        "home": hn,
        "away": an,
        "venue": venue,
        "espn_id": eid,
        "label": f"{hn} vs {an}",
    }


def _load_cache(root: Path) -> dict[str, Any]:
    p = cache_path(root)
    if not p.is_file():
        return {"version": 1, "rounds": {}}
    try:
        with p.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"version": 1, "rounds": {}}
    if not isinstance(raw.get("rounds"), dict):
        raw["rounds"] = {}
    return raw


def _write_cache(root: Path, payload: dict[str, Any]) -> None:
    write_atomic_json(cache_path(root), payload, indent=0)


def _round_entry_fixtures(entry: dict[str, Any]) -> list[dict[str, Any]]:
    fx = entry.get("fixtures")
    return list(fx) if isinstance(fx, list) else []


def _dedupe_fixtures(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    no_id: list[dict[str, Any]] = []
    for fx in fixtures:
        eid = str(fx.get("espn_id") or "")
        if eid:
            by_id[eid] = fx
        else:
            key = (fx.get("date"), fx.get("home"), fx.get("away"))
            no_id.append(fx)
    out = list(by_id.values())
    seen: set[tuple[str, str, str]] = set()
    for fx in no_id:
        key = (str(fx.get("date")), str(fx.get("home")), str(fx.get("away")))
        if key in seen:
            continue
        seen.add(key)
        out.append(fx)
    return out


def _sort_fixtures(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {r: i for i, r in enumerate(KNOCKOUT_ROUNDS_ORDER)}

    def key(fx: dict[str, Any]) -> tuple[int, str, str]:
        return (order.get(fx.get("round", ""), 99), fx.get("date") or "", fx.get("espn_id") or "")

    return sorted(fixtures, key=key)


def _rounds_needing_fetch(cache: dict[str, Any], rounds: tuple[str, ...]) -> list[str]:
    """Return round names that are not cached complete with all expected matches."""
    need: list[str] = []
    rounds_data = cache.get("rounds") or {}
    for rnd in rounds:
        entry = rounds_data.get(rnd) or {}
        if entry.get("complete") and len(_round_entry_fixtures(entry)) >= ROUND_EXPECTED[rnd]:
            continue
        need.append(rnd)
    return need


def _merge_round(cache: dict[str, Any], rnd: str, fresh: list[dict[str, Any]], idx_base: int) -> None:
    rounds_data = cache.setdefault("rounds", {})
    entry = rounds_data.get(rnd) or {"complete": False, "fixtures": []}
    merged = _dedupe_fixtures(_round_entry_fixtures(entry) + [f for f in fresh if f.get("round") == rnd])
    merged = _sort_fixtures(merged)

    next_idx = int(cache.get("next_idx") or idx_base)
    seen_idx: set[int] = set()
    for fx in merged:
        if fx.get("_idx") is not None:
            seen_idx.add(int(fx["_idx"]))
    for fx in merged:
        if fx.get("_idx") is not None:
            continue
        while next_idx in seen_idx:
            next_idx += 1
        fx["_idx"] = next_idx
        seen_idx.add(next_idx)
        next_idx += 1
    cache["next_idx"] = next_idx

    complete = len(merged) >= ROUND_EXPECTED[rnd]
    rounds_data[rnd] = {
        "complete": complete,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fixtures": merged,
    }


def refresh_knockout_cache(
    root: Path,
    *,
    rounds: tuple[str, ...] = ROUNDS_FROM_R16,
    idx_base: int = 72,
) -> dict[str, Any]:
    """Fetch ESPN when any target round is incomplete; return full cache payload."""
    cache = _load_cache(root)
    if cache.get("next_idx") is None:
        cache["next_idx"] = idx_base
    if not _rounds_needing_fetch(cache, rounds):
        return cache

    events = _fetch_scoreboard_range(_KO_FIRST, _KO_LAST)
    parsed = [_parse_resolved_event(ev) for ev in events]
    resolved = [p for p in parsed if p is not None]

    for rnd in rounds:
        _merge_round(cache, rnd, resolved, idx_base)

    # Also keep Round of 32 in cache when ESPN has real pairings (optional enrichment).
    _merge_round(cache, "Round of 32", resolved, idx_base)

    _write_cache(root, cache)
    return cache


def fixtures_from_cache(
    cache: dict[str, Any],
    *,
    rounds: tuple[str, ...] = ROUNDS_FROM_R16,
    include_r32: bool = True,
) -> list[dict[str, Any]]:
    """Flatten cached fixtures for requested rounds."""
    want: list[str] = list(rounds)
    if include_r32 and "Round of 32" not in want:
        entry = (cache.get("rounds") or {}).get("Round of 32") or {}
        if entry.get("complete") or _round_entry_fixtures(entry):
            want = ["Round of 32"] + want

    out: list[dict[str, Any]] = []
    rounds_data = cache.get("rounds") or {}
    for rnd in KNOCKOUT_ROUNDS_ORDER:
        if rnd not in want:
            continue
        entry = rounds_data.get(rnd) or {}
        out.extend(_round_entry_fixtures(entry))
    return _sort_fixtures(out)


def assign_fixture_indices(fixtures: list[dict[str, Any]], base_idx: int) -> list[dict[str, Any]]:
    """Ensure each fixture has ``_idx`` (usually already set in cache)."""
    out: list[dict[str, Any]] = []
    next_idx = base_idx
    used: set[int] = set()
    for fx in fixtures:
        row = dict(fx)
        if row.get("_idx") is not None:
            used.add(int(row["_idx"]))
        out.append(row)
    for row in out:
        if row.get("_idx") is not None:
            continue
        while next_idx in used:
            next_idx += 1
        row["_idx"] = next_idx
        used.add(next_idx)
        next_idx += 1
    return out


def get_resolved_knockout_fixtures(
    root: Path,
    today: date,
    *,
    idx_base: int,
    rounds: tuple[str, ...] = ROUNDS_FROM_R16,
    include_r32: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load/cache knockout fixtures with stable ``_idx`` from ``idx_base``; return (fixtures, cache)."""
    _ = today  # reserved for future date-gated fetch rules
    cache = refresh_knockout_cache(root, rounds=rounds, idx_base=idx_base)
    flat = fixtures_from_cache(cache, rounds=rounds, include_r32=include_r32)
    return assign_fixture_indices(flat, idx_base), cache


def round_schedule_status(cache: dict[str, Any], rnd: str) -> tuple[int, int, bool]:
    """(have, expected, complete) for a knockout round."""
    entry = (cache.get("rounds") or {}).get(rnd) or {}
    have = len(_round_entry_fixtures(entry))
    exp = ROUND_EXPECTED.get(rnd, 0)
    return have, exp, bool(entry.get("complete") and have >= exp)
