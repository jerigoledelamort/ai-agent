from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_agent(workdir: Path, repo_root: Path) -> subprocess.CompletedProcess[str]:
    cmd = (
        "from pathlib import Path; "
        "from src.runner import run; "
        f"raise SystemExit(run(Path(r'{workdir}')))"
    )
    return subprocess.run(
        ["python", "-c", cmd],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_agent_generates_project_structure(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    version_dir = tmp_path / "projects" / "sample" / "v1"
    (version_dir / "memory").mkdir(parents=True)
    (version_dir / "memory" / "task.md").write_text(
        """Агент должен анализировать ТЗ\nВход: task.md\nВыход: проект\n""",
        encoding="utf-8",
    )

    result = _run_agent(version_dir, repo_root)

    assert result.returncode == 0, result.stdout + result.stderr

    structure = json.loads((version_dir / "memory" / "file_structure.json").read_text(encoding="utf-8"))
    src_modules = structure.get("src", [])
    assert src_modules

    for module in src_modules:
        assert (version_dir / "src" / module).exists()
        assert (version_dir / "tests" / f"test_{Path(module).stem}.py").exists()

    assert (version_dir / "memory" / "plan.json").exists()
    assert (version_dir / "tests" / "test_results.md").exists()
    assert (version_dir / "memory" / "project_state.md").exists()


def test_agent_loads_previous_version_context(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    project_root = tmp_path / "projects" / "sample"
    v1 = project_root / "v1"
    v2 = project_root / "v2"

    (v1 / "memory").mkdir(parents=True)
    (v1 / "memory" / "task.md").write_text("Агент должен вести память", encoding="utf-8")
    (v1 / "memory" / "context.md").write_text("v1 context", encoding="utf-8")

    (v2 / "memory").mkdir(parents=True)
    (v2 / "memory" / "task.md").write_text("Агент должен использовать память v1", encoding="utf-8")

    result = _run_agent(v2, repo_root)

    assert result.returncode == 0, result.stdout + result.stderr
    devlog = (v2 / "memory" / "devlog.md").read_text(encoding="utf-8")
    assert "Loaded context from current and previous version" in devlog
