from __future__ import annotations

from pathlib import Path
import re

from .llm_client import generate
from .sandbox_guard import SandboxGuard


_CODE_BLOCK = re.compile(
    r"```python(?:\s+file:(?P<file>[^\n]+))?\n(?P<code>.*?)```",
    re.DOTALL,
)

_ERROR_LINE = re.compile(
    r"(SyntaxError|ImportError|ModuleNotFoundError|AttributeError|TypeError|NameError|ValueError|AssertionError).*",
    re.MULTILINE,
)

_TEST_PATH_PATTERN = re.compile(r"\btests?/[^\s:]+\.py\b")
_SRC_PATH_PATTERN = re.compile(r"\bsrc/[^\s:]+\.py\b")


class Fixer:

    def __init__(self, workdir: Path, guard: SandboxGuard) -> None:
        self.workdir = workdir
        self.guard = guard

    def _extract_errors(self, output: str) -> str:
        matches = _ERROR_LINE.findall(output)
        lines = []
        for line in output.splitlines():
            if any(err in line for err in matches):
                lines.append(line)
        return "\n".join(lines) if lines else output[:2000]

    def _classify_failure(self, output: str, context: str) -> str:
        lowered = output.lower()

        if context == "source_validation":
            if "syntaxerror" in lowered:
                return "invalid_source_syntax"
            if "importerror" in lowered or "nameerror" in lowered:
                return "invalid_source_dependencies_or_names"
            return "invalid_source_code"

        test_paths = set(_TEST_PATH_PATTERN.findall(output))
        src_paths = set(_SRC_PATH_PATTERN.findall(output))

        if "collected 0 items" in lowered and test_paths:
            return "invalid_test_code"
        if "syntaxerror" in lowered and test_paths and not src_paths:
            return "invalid_test_code"
        if "modulenotfounderror" in lowered and test_paths and not src_paths:
            return "invalid_test_code"
        if "assertionerror" in lowered and test_paths and not src_paths:
            return "invalid_test_code"
        if src_paths and any(err in lowered for err in ["nameerror", "typeerror", "attributeerror", "importerror"]):
            return "incorrect_implementation_code"
        if src_paths and "assertionerror" in lowered:
            return "incorrect_implementation_code"
        if test_paths and src_paths:
            return "mixed_test_and_implementation_failures"
        return "unknown"

    def apply(self, output: str, context: str = "pytest") -> str:

        state_path = self.guard.resolve("memory/project_state.md")
        project_state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""

        error_summary = self._extract_errors(output)
        failure_type = self._classify_failure(output, context)

        prompt = (
            f"The project failed during {context}.\n\n"
            f"Failure classification: {failure_type}\n\n"
            "Key errors:\n"
            f"{error_summary}\n\n"
            "Current project state:\n"
            f"{project_state}\n\n"
            "Fix the code based on the failure classification.\n\n"
            "IMPORTANT RULES:\n"
            "- You may modify files inside src/ and tests/.\n"
            "- Do NOT create unrelated files.\n"
            "- Keep the project generic and aligned to existing API.\n\n"
            "Return corrected code patches with explicit file hints."
        )

        response = generate(prompt)
        matches = list(_CODE_BLOCK.finditer(response))

        if not matches:
            return "No automatic fix applied."

        applied = 0
        for match in matches:
            file_hint = match.group("file")
            code = match.group("code").strip() + "\n"
            if not file_hint:
                continue

            rel = file_hint.strip()
            if not (rel.startswith("src/") or rel.startswith("tests/")):
                continue

            path = self.guard.resolve(rel)
            if not path.exists():
                continue

            path.write_text(code, encoding="utf-8")
            applied += 1

        return f"Applied {applied} LLM patch(es)." if applied else "No automatic fix applied."
