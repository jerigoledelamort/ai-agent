from __future__ import annotations

from pathlib import Path


class SandboxViolationError(RuntimeError):
    pass


class SandboxGuard:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, relative_path: str | Path) -> Path:
        candidate = (self.root / relative_path).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise SandboxViolationError(f"Path escapes sandbox: {relative_path}")
        return candidate
