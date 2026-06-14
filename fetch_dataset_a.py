"""
Dataset A – Historical international matches (martj42).

Primary source (no Kaggle login): upstream CSV maintained with the Kaggle dataset:
  https://github.com/martj42/international_results/blob/master/results.csv

Kaggle bundle (same project, requires API credentials):
  https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017

Output: data/dataset_A_international_matches.csv
Columns: date, home_team, away_team, home_score, away_score, tournament, neutral
"""

from __future__ import annotations

import argparse
import csv
import io
import shutil
import sys
import urllib.request
from pathlib import Path

KAGGLE_SLUG = "martj42/international-football-results-from-1872-to-2017"
GITHUB_RESULTS_CSV = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

SOURCE_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
]
OUTPUT_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "neutral",
]


def project_root() -> Path:
    return Path(__file__).resolve().parent


def fetch_github_results(dest_csv: Path) -> int:
    req = urllib.request.Request(
        GITHUB_RESULTS_CSV,
        headers={"User-Agent": "fifa-ml-dataset-a/1.0"},
    )
    print("Downloading", GITHUB_RESULTS_CSV, file=sys.stderr)
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = io.TextIOWrapper(resp, encoding="utf-8", newline="")
        reader = csv.DictReader(text)
        if reader.fieldnames is None:
            raise RuntimeError("CSV has no header row")
        missing = set(SOURCE_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise RuntimeError(f"Unexpected CSV headers; missing: {sorted(missing)}")

        dest_csv.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with dest_csv.open("w", newline="", encoding="utf-8") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                writer.writerow({k: row.get(k, "") for k in OUTPUT_COLUMNS})
                n += 1
    return n


def fetch_kaggle_results(dest_csv: Path, scratch: Path) -> int:
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as e:
        raise RuntimeError(
            "Kaggle source requires: pip install kaggle\n"
            "and credentials at ~/.kaggle/kaggle.json (see Kaggle account settings)."
        ) from e

    scratch.mkdir(parents=True, exist_ok=True)

    print("Downloading from Kaggle:", KAGGLE_SLUG, file=sys.stderr)
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(KAGGLE_SLUG, path=str(scratch), quiet=False, unzip=True)

    candidates = sorted(scratch.rglob("results.csv"))
    if not candidates:
        raise RuntimeError(f"No results.csv found under {scratch} after Kaggle download.")
    results_path = candidates[0]

    n = 0
    with results_path.open(newline="", encoding="utf-8") as inf, dest_csv.open(
        "w", newline="", encoding="utf-8"
    ) as outf:
        reader = csv.DictReader(inf)
        if reader.fieldnames is None:
            raise RuntimeError("CSV has no header row")
        missing = set(SOURCE_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise RuntimeError(f"Unexpected CSV headers; missing: {sorted(missing)}")
        writer = csv.DictWriter(outf, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            writer.writerow({k: row.get(k, "") for k in OUTPUT_COLUMNS})
            n += 1

    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=("github", "kaggle"),
        default="github",
        help="github: public martj42/results.csv (default). kaggle: requires kaggle API + credentials.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: data/dataset_A_international_matches.csv)",
    )
    args = parser.parse_args()

    root = project_root()
    out_path = args.output or (root / "data" / "dataset_A_international_matches.csv")

    scratch = root / "data" / ".kaggle_scratch"
    try:
        if args.source == "github":
            count = fetch_github_results(out_path)
        else:
            count = fetch_kaggle_results(out_path, scratch)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)

    print(f"Wrote {count} match rows to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
