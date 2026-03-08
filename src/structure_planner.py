from __future__ import annotations

from pathlib import Path
import json
import re

from .llm_client import generate
from .memory_manager import MemoryManager
from .sandbox_guard import SandboxGuard


_GENERIC_NAMES = {
    "main.py",
    "app.py",
    "project_app.py",
    "main_module.py",
}
_MODULE_NUMBER_PATTERN = re.compile(r"^module\d+\.py$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _is_valid_module_name(name: str) -> bool:
    if name in _GENERIC_NAMES:
        return False
    if _MODULE_NUMBER_PATTERN.match(name):
        return False
    return True


def _extract_modules_from_architecture(text: str) -> list[str]:
    """
    Extract python module names from architecture.md.
    """
    matches = re.findall(r"\b(?:src/)?([a-zA-Z_][a-zA-Z0-9_]*\.py)\b", text)
    modules: list[str] = []

    for m in matches:
        name = Path(m).name
        if name.startswith("test_"):
            continue
        if _is_valid_module_name(name):
            modules.append(name)

    return list(dict.fromkeys(modules))


def _normalize_structure(parsed: dict) -> dict:
    src = parsed.get("src") if isinstance(parsed, dict) else None
    tests = parsed.get("tests") if isinstance(parsed, dict) else None

    if not isinstance(src, list):
        src = []
    if not isinstance(tests, list):
        tests = []

    src_normalized: list[str] = []
    for item in src:
        raw = str(item)
        name = Path(raw).name

        if "/" in raw.replace("\\", "/"):
            continue
        if name.startswith("test_"):
            continue
        if not name.endswith(".py"):
            name = f"{Path(name).stem}.py"
        if not _is_valid_module_name(name):
            continue
        src_normalized.append(name)

    src_normalized = list(dict.fromkeys(src_normalized))

    tests_normalized: list[str] = []
    for item in tests:
        name = Path(str(item)).name
        if not name.endswith(".py"):
            name = f"{Path(name).stem}.py"
        if not name.startswith("test_"):
            name = f"test_{Path(name).stem}.py"
        tests_normalized.append(name)

    if src_normalized and not tests_normalized:
        tests_normalized = [f"test_{Path(module).stem}.py" for module in src_normalized]

    tests_normalized = list(dict.fromkeys(tests_normalized))

    return {
        "src": src_normalized,
        "tests": tests_normalized,
    }


def plan_file_structure(memory: MemoryManager, guard: SandboxGuard) -> dict:
    task = _read(guard.resolve("memory/task.md"))
    requirements = _read(guard.resolve("memory/requirements.md"))
    architecture = _read(guard.resolve("memory/architecture.md"))

    modules = _extract_modules_from_architecture(architecture)
    if modules:
        structure = {
            "src": modules,
            "tests": [f"test_{Path(module).stem}.py" for module in modules],
        }
        memory.write_json("file_structure.json", structure)
        return structure

    prompt = (
        "Based on the project specification, design a Python project file structure.\n\n"
        "Project specification:\n"
        f"{task}\n\n"
        "Requirements:\n"
        f"{requirements}\n\n"
        "Architecture:\n"
        f"{architecture}\n\n"
        "Rules:\n"
        "- File names must be directly grounded in architecture.md and task.md.\n"
        "- Use descriptive names derived from the domain of the task.\n"
        "- Do not use template names such as project_app.py, main_module.py, module1.py, module2.py.\n"
        "- Each module must be a single Python file inside src/.\n"
        "- Do not create nested directories inside src/.\n"
        "- Include tests only for actual src modules and match their names.\n"
        "- The structure must include src/ and tests/.\n\n"
        "Return JSON with schema:\n"
        '{"src": ["..."], "tests": ["..."]}'
    )

    response = generate(prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {}

    normalized = _normalize_structure(parsed)

    if normalized["src"] and not normalized["tests"]:
        normalized["tests"] = [f"test_{Path(module).stem}.py" for module in normalized["src"]]

    memory.write_json("file_structure.json", normalized)

    return normalized
