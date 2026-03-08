from __future__ import annotations

from pathlib import Path

from src.runner import run


if __name__ == "__main__":
    raise SystemExit(run(Path.cwd()))