from __future__ import annotations

from pathlib import Path
import difflib
import json
import re

from .llm_client import generate
from .memory_manager import MemoryManager
from .project_state import summarize_project
from .sandbox_guard import SandboxGuard


_CODE_BLOCK = re.compile(r"```python(?:\s+file:(?P<file>[^\n]+))?\n(?P<code>.*?)```", re.DOTALL)
_TRIVIAL_TEST_PATTERNS = ("assert 1 + 1 == 2", "assert True", "assert 2 + 2 == 4")
_IMPORT_FROM_PATTERN = re.compile(r"^\s*from\s+src\.([a-zA-Z_][\w]*)\s+import\s+", re.MULTILINE)
_IMPORT_PATTERN = re.compile(r"^\s*import\s+src\.([a-zA-Z_][\w]*)\b", re.MULTILINE)


class Executor:

    def _source_snippets(self) -> str:
        src_dir = self.guard.resolve("src")
        snippets = []
        for file in sorted(src_dir.glob("*.py")):
            if file.name == "__init__.py":
                continue
            code = file.read_text(encoding="utf-8")
            snippets.append(
                f"# file: src/{file.name}\n"
                f"{code}\n"
            )
        return "\n\n".join(snippets)

    def __init__(self, guard: SandboxGuard) -> None:
        self.guard = guard
        self.workdir = guard.root
        self.memory = MemoryManager(guard)

    def _extract_blocks(self, text: str) -> list[tuple[str | None, str]]:
        blocks = []
        for match in _CODE_BLOCK.finditer(text):
            file_name = match.group("file")
            code = match.group("code").strip() + "\n"
            blocks.append((file_name.strip() if file_name else None, code))
        return blocks

    def _read(self, rel: str) -> str:
        path = self.guard.resolve(rel)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _full_context(self) -> dict[str, str]:
        return {
            "task": self._read("memory/task.md"),
            "requirements": self._read("memory/requirements.md"),
            "architecture": self._read("memory/architecture.md"),
            "file_structure": self._read("memory/file_structure.json"),
            "project_state": self._read("memory/project_state.md"),
        }

    def _load_file_structure(self) -> dict[str, list[str]]:
        path = self.guard.resolve("memory/file_structure.json")

        if not path.exists():
            return {
                "src": ["module1.py"],
                "tests": ["test_module.py"],
            }

        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "src": ["module1.py"],
                "tests": ["test_module.py"],
            }

        src = parsed.get("src")
        tests = parsed.get("tests")

        if not isinstance(src, list) or not src:
            src = ["module1.py"]

        if not isinstance(tests, list) or not tests:
            tests = ["test_module.py"]

        return {"src": src, "tests": tests}

    def _update_state(self):
        state = summarize_project(self.workdir, self.guard)
        self.memory.write_text("project_state.md", state)

    def _module_list(self) -> str:
        src_dir = self.guard.resolve("src")

        modules = []
        if src_dir.exists():
            for p in sorted(src_dir.glob("*.py")):
                if p.name != "__init__.py":
                    modules.append(f"src/{p.name}")

        return "Existing project modules:\n" + "\n".join(modules)

    def generate_structure_from_plan(self) -> list[Path]:

        structure = self._load_file_structure()

        src_dir = self.guard.resolve("src")
        tests_dir = self.guard.resolve("tests")

        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)

        generated = []

        for module in structure["src"]:
            if module.startswith("test_"):
                continue
            path = self.guard.resolve(f"src/{module}")
            path.parent.mkdir(parents=True, exist_ok=True)

            class_name = Path(module).stem.capitalize()

            skeleton = (
                f"class {class_name}:\n"
                "    def __init__(self):\n"
                "        pass\n"
            )

            path.write_text(skeleton, encoding="utf-8")
            generated.append(path)

        init_file = self.guard.resolve("src/__init__.py")
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

        self._update_state()
        self.memory.append_devlog("Structure phase completed")

        return generated

    def implement_modules(self) -> list[Path]:

        structure = self._load_file_structure()

        generated = []

        for module in structure["src"]:

            context = self._full_context()

            prompt = (
                "Project specification:\n"
                f"{context['task']}\n\n"

                "Requirements:\n"
                f"{context['requirements']}\n\n"

                "Architecture:\n"
                f"{context['architecture']}\n\n"

                "Project file structure:\n"
                f"{context['file_structure']}\n\n"

                "Current project state:\n"
                f"{context['project_state']}\n\n"

                "Current project source code:\n"
                f"{self._source_snippets()}\n\n"

                f"{self._module_list()}\n\n"

                f"Implement functionality for this module: src/{module}\n\n"

                "Rules:\n"
                "- Only modify this module.\n"
                "- Do not break existing functions.\n"
                "- Use existing modules if possible.\n"
                "- Only import modules from the list above.\n"
                "- Do not reference modules that do not exist.\n"
            )

            response = generate(prompt)

            blocks = self._extract_blocks(response)

            code = ""

            for file_hint, block in blocks:
                if file_hint == f"src/{module}":
                    code = block
                    break

            if not code and blocks:
                code = blocks[0][1]

            path = self.guard.resolve(f"src/{module}")
            path.write_text(code, encoding="utf-8")

            generated.append(path)

            self._update_state()

        self.memory.append_devlog("Implementation phase completed")

        return generated

    def validate_dependencies(self) -> list[Path]:
        src_dir = self.guard.resolve("src")
        available = [
            p.stem
            for p in src_dir.glob("*.py")
            if p.name != "__init__.py"
        ]
        corrected = []
        for file_path in src_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue
            content = file_path.read_text(encoding="utf-8")
            original = content
            for module in _IMPORT_FROM_PATTERN.findall(content):
                if module not in available:
                    replacement = difflib.get_close_matches(module, available, n=1)[0]
                    content = content.replace(
                        f"from src.{module}",
                        f"from src.{replacement}"
                    )
            for module in _IMPORT_PATTERN.findall(content):
                if module not in available:
                    replacement = difflib.get_close_matches(module, available, n=1)[0]
                    content = content.replace(
                        f"import src.{module}",
                        f"import src.{replacement}"
                    )
            if content != original:
                file_path.write_text(content, encoding="utf-8")
                corrected.append(file_path)
        return corrected

    def generate_tests_from_structure(self) -> list[Path]:

        context = self._full_context()
        structure = self._load_file_structure()

        tests_dir = self.guard.resolve("tests")
        tests_dir.mkdir(parents=True, exist_ok=True)

        allowed_tests = set(structure["tests"])

        imports = "\n".join(
            f"from src.{Path(module).stem} import *"
            for module in structure["src"]
        )

        prompt = (
            "Project specification:\n"
            f"{context['task']}\n\n"
            "Project source code:\n"
            f"{self._source_snippets()}\n\n"
            "Existing tests:\n"
            f"{self._existing_tests()}\n\n"
            f"{self._module_list()}\n\n"
            "Generate pytest tests for the project.\n\n"
            "IMPORTANT RULES:\n"
            "Tests must be written only for the files defined in the project structure.\n"
            f"Allowed test files: {', '.join(allowed_tests)}\n"
            "Do not create additional test files.\n"
            "Do not reference modules that do not exist.\n\n"
            "If tests already exist, extend them instead of replacing them.\n"
            "Do not delete existing tests.\n"
            f"Suggested imports:\n{imports}\n"
        )

        response = generate(prompt)

        blocks = self._extract_blocks(response)

        valid_code = None

        for file_hint, block in blocks:

            if not file_hint:
                continue

            filename = Path(file_hint).name

            if filename in allowed_tests:
                valid_code = block
                test_name = filename
                break

        # fallback если LLM вернул мусор
        if not valid_code:

            test_name = structure["tests"][0]

            valid_code = (
                "def test_placeholder():\n"
                "    assert True\n"
            )

        test_file = self.guard.resolve(f"tests/{test_name}")
        existing = ""
        if test_file.exists():
            existing = test_file.read_text(encoding="utf-8")
        if existing and valid_code not in existing:
            valid_code = existing + "\n\n" + valid_code
        test_file.write_text(valid_code, encoding="utf-8")

        self._update_state()
        self.memory.append_devlog("Test generation phase completed")

        return [test_file]
    
    def _existing_tests(self) -> str:

        tests_dir = self.guard.resolve("tests")

        snippets = []

        if tests_dir.exists():
            for file in sorted(tests_dir.glob("*.py")):
                code = file.read_text(encoding="utf-8")
                snippets.append(
                    f"# file: tests/{file.name}\n"
                    f"{code}\n"
                )

        return "\n\n".join(snippets)