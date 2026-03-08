from __future__ import annotations

import subprocess
from pathlib import Path


def _run_agent(workdir: Path, repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(repo_root / "agent.py")],
        cwd=workdir,
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
    assert (version_dir / "src" / "project_app.py").exists()
    assert (version_dir / "tests" / "test_project_app.py").exists()
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
