from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class TestResult:
    success: bool
    output: str


class Tester:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir

    def _discover_test_targets(self) -> list[str]:
        src_dir = self.workdir / "src"
        tests_dir = self.workdir / "tests"

        if not tests_dir.exists():
            return []

        modules = {
            path.stem
            for path in src_dir.glob("*.py")
            if path.name != "__init__.py"
        }

        if not modules:
            return sorted(str(path.relative_to(self.workdir)) for path in tests_dir.glob("test_*.py"))

        targets: list[str] = []
        for module in sorted(modules):
            test_file = tests_dir / f"test_{module}.py"
            if test_file.exists():
                targets.append(str(test_file.relative_to(self.workdir)))

        if not targets:
            targets = sorted(str(path.relative_to(self.workdir)) for path in tests_dir.glob("test_*.py"))

        return targets

    def run(self) -> TestResult:
        targets = self._discover_test_targets()
        cmd = ["python", "-m", "pytest", "-q"]
        cmd.extend(targets)

        result = subprocess.run(
            cmd,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return TestResult(success=result.returncode == 0, output=output.strip())
