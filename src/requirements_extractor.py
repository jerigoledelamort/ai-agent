from __future__ import annotations

from .llm_client import generate, parse_python_list
from .sandbox_guard import SandboxGuard


def _read_project_state(guard: SandboxGuard | None) -> str:
    if not guard:
        return ""
    state_path = guard.resolve("memory/project_state.md")
    if not state_path.exists():
        return ""
    return state_path.read_text(encoding="utf-8")


def extract_requirements(task_text: str, guard: SandboxGuard | None = None) -> list[str]:
    project_state = _read_project_state(guard)
    prompt = (
        "Extract structured software requirements from the following specification.\n\n"
        "Return a bullet list.\n\n"
        "Specification:\n"
        f"{task_text}\n\n"
        "Current project state:\n"
        f"{project_state}\n\n"
        "Return Python list of requirements."
    )
    response = generate(prompt)
    parsed = parse_python_list(response)
    if parsed:
        return parsed
    lines = [line.strip("- ") for line in response.splitlines() if line.strip()]
    return lines if lines else ["Реализовать требования из memory/task.md."]
