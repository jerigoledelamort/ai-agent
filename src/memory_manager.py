from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from .sandbox_guard import SandboxGuard


class MemoryManager:
    def __init__(self, guard: SandboxGuard) -> None:
        self.guard = guard
        self.memory_dir = self.guard.resolve("memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def write_text(self, name: str, content: str) -> Path:
        path = self.guard.resolve(Path("memory") / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return path

    def write_json(self, name: str, payload: dict[str, Any]) -> Path:
        path = self.guard.resolve(Path("memory") / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def append_devlog(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        path = self.guard.resolve("memory/devlog.md")
        with path.open("a", encoding="utf-8") as out:
            out.write(f"- {stamp} {message}\n")
