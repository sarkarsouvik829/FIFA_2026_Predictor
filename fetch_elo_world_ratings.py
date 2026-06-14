"""
Download current world Elo ratings from eloratings.net (World.tsv + en.teams.tsv)
and write a UTF-8 CSV suitable for ML pipelines.

Data terms / attribution: https://eloratings.net/
"""

from __future__ import annotations

import csv
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://eloratings.net/"
WORLD_TSV = BASE + "World.tsv"
TEAMS_TSV = BASE + "en.teams.tsv"

# Column layout matches scripts/ratings.js pushRatingRow() for the World page.
HEADERS = [
    "local_rank",
    "world_rank",
    "team_code",
    "rating",
    "highest_rank",
    "highest_rating",
    "average_rank",
    "average_rating",
    "lowest_rank",
    "lowest_rating",
    "rank_change_3mo",
    "rating_change_3mo",
    "rank_change_6mo",
    "rating_change_6mo",
    "rank_change_1yr",
    "rating_change_1yr",
    "rank_change_2yr",
    "rating_change_2yr",
    "rank_change_5yr",
    "rating_change_5yr",
    "rank_change_10yr",
    "rating_change_10yr",
    "matches_total",
    "matches_home",
    "matches_away",
    "matches_neutral",
    "wins",
    "losses",
    "draws",
    "goals_for",
    "goals_against",
    "rank_change_recent",
    "rating_change_recent",
    "team_name",
    "ratings_as_of_utc",
]


def normalize_signed_number(s: str) -> str:
    """Turn site strings like '+3', '\u221215', '0' into plain signed ASCII numbers."""
    s = s.strip().replace("\u2212", "-").replace("−", "-")
    if s.startswith("+"):
        s = s[1:]
    return s


def load_team_names(text: str) -> dict[str, str]:
    """Map team code -> primary English label (first name column in en.teams.tsv)."""
    names: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0].strip()
        if not code or re.match(r".*_loc$", code):
            continue
        variants = [p for p in parts[1:] if p.strip()]
        names[code] = variants[0] if variants else code
    return names


def fetch_text(url: str) -> tuple[str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "elo-ml-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        lm = resp.headers.get("Last-Modified")
    return raw, lm


def parse_http_date(last_modified: str | None) -> str:
    if not last_modified:
        return ""
    try:
        dt = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S GMT")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return last_modified


def main() -> int:
    out_path = Path(__file__).resolve().parent / "data" / "elo_world_ratings.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching", TEAMS_TSV, file=sys.stderr)
    teams_raw, _ = fetch_text(TEAMS_TSV)
    team_names = load_team_names(teams_raw)

    print("Fetching", WORLD_TSV, file=sys.stderr)
    world_raw, last_mod = fetch_text(WORLD_TSV)
    as_of = parse_http_date(last_mod)

    rows_out: list[list[str]] = []
    for line in world_raw.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        # Some rows may omit trailing change columns; pad to 33 data columns (0..32).
        while len(fields) < 33:
            fields.append("")
        if len(fields) > 33:
            fields = fields[:33]

        code = fields[2].strip()
        name = team_names.get(code, code)

        def normalize_cell(i: int, val: str) -> str:
            val = val.strip()
            if i <= 1 or i == 2:
                return val.replace("\u2212", "-").replace("−", "-")
            return normalize_signed_number(val)

        normalized = [normalize_cell(i, val) for i, val in enumerate(fields)]

        row = normalized + [name, as_of]
        rows_out.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
