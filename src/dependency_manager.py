from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path


class DependencyManager:
    def __init__(self) -> None:
        self._stdlib_modules = set(getattr(sys, "stdlib_module_names", set()))

    def scan_imports(self, src_path: Path) -> set[str]:
        """Return imported top-level modules from source files."""
        modules: set[str] = set()

        if not src_path.exists():
            return modules

        local_modules = {
            file.stem
            for file in src_path.rglob("*.py")
            if file.name != "__init__.py"
        }

        for file in src_path.rglob("*.py"):
            try:
                tree = ast.parse(file.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split(".", 1)[0]
                        if top_level != "src":
                            modules.add(top_level)
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue
                    if not node.module:
                        continue
                    top_level = node.module.split(".", 1)[0]
                    if top_level != "src":
                        modules.add(top_level)

        modules -= local_modules
        return modules

    def detect_missing(self, modules: set[str]) -> list[str]:
        """Return modules that are not installed."""
        missing: list[str] = []

        for module in sorted(modules):
            if module in self._stdlib_modules:
                continue
            if module.startswith("_"):
                continue

            if importlib.util.find_spec(module) is None:
                missing.append(module)

        return missing

    def install(self, packages: list[str]) -> None:
        """Install packages using pip."""
        for package in packages:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=False,
                capture_output=True,
                text=True,
            )
