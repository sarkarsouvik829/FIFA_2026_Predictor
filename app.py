"""Launch the Streamlit UI (plan entrypoint)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    app = ROOT / "src" / "app.py"
    subprocess.check_call([sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]])


if __name__ == "__main__":
    main()
