from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.dependency_manager import DependencyManager
from src.runner import _extract_missing_module


def test_dependency_manager_scans_imports_and_ignores_local_and_relative(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "local_mod.py").write_text("value = 1\n", encoding="utf-8")
    (src_dir / "main.py").write_text(
        (
            "import os\n"
            "import pygame\n"
            "import src.local_mod\n"
            "from flask import Flask\n"
            "from .local_mod import value\n"
            "from local_mod import value\n"
        ),
        encoding="utf-8",
    )

    manager = DependencyManager()
    modules = manager.scan_imports(src_dir)

    assert "pygame" in modules
    assert "flask" in modules
    assert "os" in modules
    assert "local_mod" not in modules
    assert "src" not in modules


def test_dependency_manager_detect_missing_filters_stdlib() -> None:
    manager = DependencyManager()

    missing = manager.detect_missing({"json", "module_that_should_not_exist_12345"})

    assert "json" not in missing
    assert "module_that_should_not_exist_12345" in missing


def test_extract_missing_module_from_error_output() -> None:
    output = "ModuleNotFoundError: No module named 'pygame'"
    assert _extract_missing_module(output) == "pygame"

    import_error = 'ImportError: No module named "flask.cli"'
    assert _extract_missing_module(import_error) == "flask"
