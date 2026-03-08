from __future__ import annotations

from pathlib import Path
import json
import re

from .llm_client import generate
from .memory_manager import MemoryManager
from .sandbox_guard import SandboxGuard


_DEFAULT_STRUCTURE = {
    "src": ["module1.py", "module2.py"],
    "tests": ["test_module.py"],
}

_GENERIC_NAMES = {"project_app.py", "main_module.py", "main.py", "app.py"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _extract_modules_from_architecture(text: str) -> list[str]:
    """
    Extract python module names from architecture.md.
    """

    matches = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*\.py)\b", text)

    modules = []

    for m in matches:
        name = Path(m).name
        if name not in _GENERIC_NAMES:
            modules.append(name)

    # remove duplicates
    return list(dict.fromkeys(modules))


def _normalize_structure(parsed: dict) -> dict:

    src = parsed.get("src") if isinstance(parsed, dict) else None
    tests = parsed.get("tests") if isinstance(parsed, dict) else None

    if not isinstance(src, list) or not src:
        return dict(_DEFAULT_STRUCTURE)

    if not isinstance(tests, list) or not tests:
        tests = _DEFAULT_STRUCTURE["tests"]

    src_normalized: list[str] = []

    for item in src:

        name = Path(str(item)).name

        if "/" in str(item).replace("\\", "/"):
            continue

        if name.startswith("test_"):
            continue

        if not name.endswith(".py"):
            name = f"{Path(name).stem}.py"

        if name in _GENERIC_NAMES:
            continue

        src_normalized.append(name)

    if not src_normalized:
        return dict(_DEFAULT_STRUCTURE)

    tests_normalized: list[str] = []

    for item in tests:

        name = Path(str(item)).name

        if not name.endswith(".py"):
            name = f"{Path(name).stem}.py"

        tests_normalized.append(name)

    if not tests_normalized:
        tests_normalized = _DEFAULT_STRUCTURE["tests"]

    return {
        "src": src_normalized,
        "tests": tests_normalized,
    }


def plan_file_structure(memory: MemoryManager, guard: SandboxGuard) -> dict:

    task = _read(guard.resolve("memory/task.md"))
    requirements = _read(guard.resolve("memory/requirements.md"))
    architecture = _read(guard.resolve("memory/architecture.md"))

    # --- STEP 1: try extracting modules from architecture ---
    modules = _extract_modules_from_architecture(architecture)

    if modules:
        structure = {
            "src": modules,
            "tests": ["test_" + Path(modules[0]).stem + ".py"]
        }

        memory.write_json("file_structure.json", structure)
        return structure

    # --- STEP 2: fallback to LLM planning ---
    prompt = (
        "Based on the project specification, design a Python project file structure.\n\n"

        "Project specification:\n"
        f"{task}\n\n"

        "Requirements:\n"
        f"{requirements}\n\n"

        "Architecture:\n"
        f"{architecture}\n\n"

        "Rules:\n"
        "- Each module should represent a logical component of the system.\n"
        "- Use descriptive names derived from the domain of the task.\n"
        "- Avoid generic names like project_app.py or main_module.py.\n"
        "- Avoid using names from previous projects unless they are relevant.\n"
        "- Each module must be a single Python file inside src/.\n"
        "- Do not create nested directories inside src/.\n"
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

    memory.write_json("file_structure.json", normalized)

    return normalized