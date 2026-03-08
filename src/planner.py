from __future__ import annotations

import json

from .llm_client import generate
from .sandbox_guard import SandboxGuard


def _read_project_state(guard: SandboxGuard | None) -> str:
    if not guard:
        return ""
    state_path = guard.resolve("memory/project_state.md")
    if not state_path.exists():
        return ""
    return state_path.read_text(encoding="utf-8")


def create_plan(architecture: str, guard: SandboxGuard | None = None) -> dict[str, list[str]]:
    project_state = _read_project_state(guard)
    prompt = (
        "Create a step-by-step implementation plan for this architecture.\n\n"
        "Architecture:\n"
        f"{architecture}\n\n"
        "Current project state:\n"
        f"{project_state}\n\n"
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
    return {"steps": ["implement src", "generate tests", "run tests"]}
