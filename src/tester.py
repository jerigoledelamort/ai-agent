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

    def run(self) -> TestResult:
        result = subprocess.run(
            ["python", "-m", "pytest", "-q"],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return TestResult(success=result.returncode == 0, output=output.strip())
