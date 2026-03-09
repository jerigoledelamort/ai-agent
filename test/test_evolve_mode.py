from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.executor import Executor
from src.project_analyzer import analyze_project
from src.runner import detect_task_mode
from src.sandbox_guard import SandboxGuard


def test_detect_task_mode_build_and_evolve() -> None:
    assert detect_task_mode("Create a new project from specification") == "build"
    assert detect_task_mode("Analyze existing project and refactor architecture") == "evolve"


def test_project_analyzer_collects_modules_and_dependencies(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "module_a.py").write_text("import module_b\n\ndef run():\n    return 1\n", encoding="utf-8")
    (src_dir / "module_b.py").write_text("class Service:\n    pass\n", encoding="utf-8")

    graph = analyze_project(SandboxGuard(tmp_path))

    assert "module_a" in graph["modules"]
    assert graph["modules"]["module_a"]["functions"] == ["run"]
    assert "module_b" in graph["modules"]
    assert graph["dependency_graph"]["module_a"] == ["module_b"]


def test_executor_apply_refactor_updates_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "memory").mkdir()
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "mod.py"
    target.write_text("import os\n\n\ndef f():\n    return 1\n", encoding="utf-8")

    def fake_generate(prompt: str) -> str:
        if "Remove only unused imports" in prompt:
            return "```python file:src/mod.py\n\ndef f():\n    return 1\n```"
        return "```python file:src/mod.py\ndef f():\n    return 2\n```"

    monkeypatch.setattr("src.executor.generate", fake_generate)

    executor = Executor(SandboxGuard(tmp_path))
    applied = executor.apply_refactor(
        {
            "actions": [
                {"type": "remove_unused_import", "target": "src/mod.py", "description": "clean imports"},
                {"type": "update_function", "target": "src/mod.py", "description": "change return"},
            ]
        }
    )

    assert applied
    assert "return 2" in target.read_text(encoding="utf-8")
