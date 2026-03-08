from __future__ import annotations

from pathlib import Path

from .sandbox_guard import SandboxGuard


def summarize_project(workdir: Path, guard: SandboxGuard | None = None) -> str:
    resolver = guard.resolve if guard else lambda p: (workdir / p).resolve()
    src = resolver("src")
    tests = resolver("tests")

    modules: list[str] = []
    if src.exists():
        for file_path in sorted(src.glob("*.py")):
            modules.append(f"src/{file_path.name}")

    test_files: list[str] = []
    if tests.exists():
        for file_path in sorted(tests.glob("*.py")):
            test_files.append(f"tests/{file_path.name}")

    text = "# Project State\n\n"
    text += "## Modules\n"
    for module in modules:
        text += f"- {module}\n"

    text += "\n## Tests\n"
    for test_file in test_files:
        text += f"- {test_file}\n"

    text += "\n## Notes\nGenerated automatically.\n"
    return text
