from __future__ import annotations

from pathlib import Path

from agent import run


if __name__ == "__main__":
    raise SystemExit(run(Path.cwd()))
