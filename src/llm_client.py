from __future__ import annotations

import ast
import json
import subprocess

MODEL = "qwen2.5-coder:14b"


def _fallback(prompt: str) -> str:
    if "Return Python list of requirements" in prompt:
        return "['Агент должен анализировать ТЗ', 'Вход: task.md', 'Выход: работоспособный программный проект']"
    if "Return JSON" in prompt:
        return json.dumps(
            {
                "steps": [
                    "create src package",
                    "implement core project module",
                    "generate pytest tests",
                    "run tests",
                ]
            },
            ensure_ascii=False,
        )
    if "Generate pytest tests for the following module" in prompt:
        return """```python
from src.project_app import ProjectState, is_project_complete


def test_complete_state():
    state = ProjectState(steps_done=4, total_steps=4, tests_passed=True, active_errors=0)
    assert is_project_complete(state) is True


def test_not_complete_with_errors():
    state = ProjectState(steps_done=4, total_steps=4, tests_passed=True, active_errors=1)
    assert is_project_complete(state) is False
```
"""
    if "Fix the code" in prompt:
        return """```python
from src.project_app import ProjectState, is_project_complete


def test_complete_state():
    state = ProjectState(steps_done=4, total_steps=4, tests_passed=True, active_errors=0)
    assert is_project_complete(state) is True


def test_not_complete_with_errors():
    state = ProjectState(steps_done=4, total_steps=4, tests_passed=True, active_errors=1)
    assert is_project_complete(state) is False
```
"""
    if "Implement the following step" in prompt:
        return """```python file:src/project_app.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProjectState:
    steps_done: int
    total_steps: int
    tests_passed: bool
    active_errors: int


def is_project_complete(state: ProjectState) -> bool:
    return (
        state.total_steps > 0
        and state.steps_done >= state.total_steps
        and state.tests_passed
        and state.active_errors == 0
    )
```
```python file:src/__init__.py
```
"""
    if "Return markdown" in prompt:
        return """# Architecture

## Modules
- context_loader.py: context loading
- requirements_extractor.py: requirements extraction
- architect.py: architecture generation
- planner.py: planning
- executor.py: code generation
- tester.py: testing
- fixer.py: bug fixing

## File structure
- src/project_app.py
- tests/test_project_app.py

## Interfaces
- run(workdir)
- generate(prompt)
"""
    return ""


def generate(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", MODEL],
            input=prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("Ollama not found. Make sure Ollama is installed and available in PATH.")
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(
        f"LLM generation failed.\n"
        f"Return code: {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def parse_python_list(text: str) -> list[str]:
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []
