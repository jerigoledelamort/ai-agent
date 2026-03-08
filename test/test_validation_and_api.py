from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api_extractor import extract_api_from_source
from src.source_validator import validate_source_directory


def test_source_validator_reports_syntax_and_import_errors(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "broken.py").write_text("def bad(:\n    pass\n", encoding="utf-8")
    (src_dir / "consumer.py").write_text("from src.missing import x\n", encoding="utf-8")

    issues = validate_source_directory(src_dir)

    assert any(issue["error_type"] == "SyntaxError" and issue["file"].endswith("broken.py") for issue in issues)
    assert any(issue["error_type"] == "ImportError" and issue["file"].endswith("consumer.py") for issue in issues)


def test_api_extractor_returns_classes_functions_and_public_methods(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "module_a.py").write_text(
        """
class Service:
    def run(self, value, retries=1):
        return value

    def _hidden(self):
        return None


def process(data):
    return data
""".strip()
        + "\n",
        encoding="utf-8",
    )

    api = extract_api_from_source(src_dir)

    module = api["modules"]["module_a"]
    assert any(func["name"] == "process" for func in module["functions"])
    assert "Service" in module["classes"]
    methods = module["classes"]["Service"]["methods"]
    assert any(method["name"] == "run" for method in methods)
    assert module["classes"]["Service"]["public_methods"] == ["run"]
