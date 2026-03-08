from __future__ import annotations

from pathlib import Path
import re

from .llm_client import generate
from .sandbox_guard import SandboxGuard


_CODE_BLOCK = re.compile(
    r"```python(?:\s+file:(?P<file>[^\n]+))?\n(?P<code>.*?)```",
    re.DOTALL,
)

# ищем ключевые ошибки из pytest
_TRACEBACK_ERROR = re.compile(
    r"(ImportError|ModuleNotFoundError|AttributeError|TypeError|NameError|ValueError).*",
    re.MULTILINE,
)


class Fixer:

    def __init__(self, workdir: Path, guard: SandboxGuard) -> None:
        self.workdir = workdir
        self.guard = guard

    def _extract_errors(self, output: str) -> str:
        """
        Извлекает ключевые ошибки из pytest output,
        чтобы LLM не получал тонны лишнего текста.
        """

        matches = _TRACEBACK_ERROR.findall(output)

        lines = []

        for line in output.splitlines():
            if any(err in line for err in matches):
                lines.append(line)

        return "\n".join(lines) if lines else output[:2000]

    def apply(self, output: str) -> str:

        state_path = self.guard.resolve("memory/project_state.md")
        project_state = (
            state_path.read_text(encoding="utf-8")
            if state_path.exists()
            else ""
        )

        error_summary = self._extract_errors(output)

        prompt = (
            "The project failed tests.\n\n"
            "Key errors:\n"
            f"{error_summary}\n\n"
            "Current project state:\n"
            f"{project_state}\n\n"
            "Fix the source code.\n\n"
            "IMPORTANT RULES:\n"
            "- Only modify files inside src/.\n"
            "- Do NOT modify tests.\n"
            "- Do NOT create new files.\n\n"
            "Return corrected code patches."
        )

        response = generate(prompt)

        matches = list(_CODE_BLOCK.finditer(response))

        if not matches:
            return "No automatic fix applied."

        applied = 0

        for match in matches:

            file_hint = match.group("file")
            code = match.group("code").strip() + "\n"

            # если модель не указала файл — пропускаем
            if not file_hint:
                continue

            rel = file_hint.strip()

            # разрешаем править только src
            if not rel.startswith("src/"):
                continue

            path = self.guard.resolve(rel)

            if not path.exists():
                continue

            path.write_text(code, encoding="utf-8")
            applied += 1

        return (
            f"Applied {applied} LLM patch(es)."
            if applied
            else "No automatic fix applied."
        )