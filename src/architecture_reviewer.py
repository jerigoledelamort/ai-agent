from __future__ import annotations

import json
from pathlib import Path

from .llm_client import generate


def _collect_file_structure(root: Path) -> list[str]:
    paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        paths.append(str(rel))
    return paths


def generate_architecture_review(task_specification: str, project_graph: dict, project_root: Path) -> str:
    file_structure = _collect_file_structure(project_root)
    prompt = (
        "You are reviewing a Python project architecture in a generic way.\n"
        "Find structural and implementation weaknesses without assuming any fixed module names.\n\n"
        "Task specification:\n"
        f"{task_specification}\n\n"
        "Project graph (JSON):\n"
        f"{json.dumps(project_graph, ensure_ascii=False, indent=2)}\n\n"
        "File structure:\n"
        + "\n".join(f"- {item}" for item in file_structure)
        + "\n\nReturn markdown with sections for: architectural problems, boundaries, dependencies,"
        " unused code, incomplete implementations, spec deviations, and runtime risks."
    )
    return generate(prompt)
