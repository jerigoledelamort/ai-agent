from __future__ import annotations

from pathlib import Path
import json
import re

from .llm_client import generate
from .sandbox_guard import SandboxGuard


def _read_project_state(guard: SandboxGuard | None) -> str:
    if not guard:
        return ""
    state_path = guard.resolve("memory/project_state.md")
    if not state_path.exists():
        return ""
    return state_path.read_text(encoding="utf-8")


def _extract_modules_from_architecture(architecture: str) -> list[str]:
    matches = re.findall(r"\b(?:src/)?([a-zA-Z_][a-zA-Z0-9_]*\.py)\b", architecture)
    modules = [Path(item).name for item in matches if not Path(item).name.startswith("test_")]
    return list(dict.fromkeys(modules))


def _fallback_steps_from_architecture(architecture: str) -> list[str]:
    modules = _extract_modules_from_architecture(architecture)
    steps: list[str] = ["analyze architecture and dependencies"]

    for module in modules:
        steps.append(f"implement src/{module}")

    steps.extend(
        [
            "generate tests for implemented modules",
            "run test suite",
        ]
    )

    return steps


def create_plan(architecture: str, guard: SandboxGuard | None = None) -> dict[str, list[str]]:
    project_state = _read_project_state(guard)
    prompt = (
        "Create a domain-agnostic step-by-step implementation plan for this architecture.\n\n"
        "Architecture:\n"
        f"{architecture}\n\n"
        "Current project state:\n"
        f"{project_state}\n\n"
        "Rules:\n"
        "- Steps must be independent of any specific domain examples.\n"
        "- Steps must refer only to architecture-defined modules/components.\n"
        "- Do not invent placeholder modules.\n\n"
        "Return JSON:\n\n"
        "{\n"
        '  "steps": [\n'
        '    "..."\n'
        "  ]\n"
        "}"
    )
    response = generate(prompt)
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {}
    steps = parsed.get("steps") if isinstance(parsed, dict) else None
    if isinstance(steps, list) and steps:
        return {"steps": [str(item) for item in steps]}
    return {"steps": _fallback_steps_from_architecture(architecture)}
