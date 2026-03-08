from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MEMORY_FILES = [
    "task.md",
    "requirements.md",
    "architecture.md",
    "plan.json",
    "context.md",
    "devlog.md",
    "bugs.md",
    "blocked.md",
]


@dataclass
class ContextBundle:
    task_text: str
    current_memory: dict[str, str]
    previous_memory: dict[str, str]


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_context(current_dir: Path, previous_dir: Path | None) -> ContextBundle:
    current_memory = {
        name: _read_optional(current_dir / "memory" / name) for name in MEMORY_FILES
    }
    previous_memory: dict[str, str] = {}
    if previous_dir:
        previous_memory = {
            name: _read_optional(previous_dir / "memory" / name) for name in MEMORY_FILES
        }

    task = _read_optional(current_dir / "memory" / "task.md")
    return ContextBundle(
        task_text=task,
        current_memory=current_memory,
        previous_memory=previous_memory,
    )
