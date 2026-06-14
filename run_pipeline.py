#!/usr/bin/env python3
"""End-to-end: historical Elo → training CSV → train models → (optional) Monte Carlo."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), file=sys.stderr)
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-elo", action="store_true")
    p.add_argument("--skip-train", action="store_true")
    p.add_argument("--skip-mc", action="store_true")
    p.add_argument("--mc-runs", type=int, default=100_000)
    p.add_argument("--mc-quick", action="store_true", help="Run 1000 MC sims only")
    p.add_argument("--mc-workers", type=int, default=None, help="Thread workers for Monte Carlo")
    args = p.parse_args()

    py = sys.executable

    if not args.skip_elo:
        run([py, str(ROOT / "build_historical_elo.py")])
        run([py, "-m", "src.dataset_builder"])

    if not args.skip_train:
        run([py, "-m", "src.train_model"])

    if not args.skip_mc:
        n = 1000 if args.mc_quick else args.mc_runs
        cmd = [py, "-m", "src.monte_carlo", "-n", str(n), "-o", str(ROOT / "outputs" / "monte_carlo_results.csv")]
        if args.mc_workers:
            cmd.extend(["--workers", str(args.mc_workers)])
        run(cmd)

    print("Pipeline finished.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
