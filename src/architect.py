from __future__ import annotations

from .llm_client import generate
from .sandbox_guard import SandboxGuard


def _read_project_state(guard: SandboxGuard | None) -> str:
    if not guard:
        return ""
    state_path = guard.resolve("memory/project_state.md")
    if not state_path.exists():
        return ""
    return state_path.read_text(encoding="utf-8")


def build_architecture(requirements: list[str], guard: SandboxGuard | None = None) -> str:
    project_state = _read_project_state(guard)
    prompt = (
        "Design a software architecture for the following requirements.\n\n"
        "Requirements:\n"
        f"{requirements}\n\n"
        "Current project state:\n"
        f"{project_state}\n\n"
        "The architecture must include:\n\n"
        "- modules\n"
        "- responsibilities\n"
        "- file structure\n"
        "- interfaces\n\n"
        "Return markdown."
    )
    response = generate(prompt)
    return response if response.strip() else "# Architecture\n"
