from __future__ import annotations

from pathlib import Path
import difflib
import json
import re

from .llm_client import generate
from .memory_manager import MemoryManager
from .project_state import summarize_project
from .sandbox_guard import SandboxGuard
from .source_validator import validate_source_directory
from .api_extractor import extract_api_from_source


_CODE_BLOCK = re.compile(r"```python(?:\s+file:(?P<file>[^\n]+))?\n(?P<code>.*?)```", re.DOTALL)
_IMPORT_FROM_PATTERN = re.compile(r"^\s*from\s+src\.([a-zA-Z_][\w]*)\s+import\s+", re.MULTILINE)
_IMPORT_PATTERN = re.compile(r"^\s*import\s+src\.([a-zA-Z_][\w]*)\b", re.MULTILINE)
_ARCH_MODULE_PATTERN = re.compile(r"\b(?:src/)?([a-zA-Z_][a-zA-Z0-9_]*\.py)\b")


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
            "api_description": self._read("memory/api_description.json"),
        }

    def _extract_modules_from_architecture(self) -> list[str]:
        architecture = self._read("memory/architecture.md")
        matches = _ARCH_MODULE_PATTERN.findall(architecture)
        modules: list[str] = []
        for item in matches:
            name = Path(item).name
            if name.startswith("test_"):
                continue
            modules.append(name)
        return list(dict.fromkeys(modules))

    def _load_file_structure(self) -> dict[str, list[str]]:
        path = self.guard.resolve("memory/file_structure.json")

        parsed: dict = {}
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                parsed = {}

        src = parsed.get("src") if isinstance(parsed, dict) else None
        tests = parsed.get("tests") if isinstance(parsed, dict) else None

        src_modules: list[str] = []
        if isinstance(src, list):
            for item in src:
                name = Path(str(item)).name
                if name and not name.startswith("test_"):
                    src_modules.append(name if name.endswith(".py") else f"{Path(name).stem}.py")

        if not src_modules:
            src_modules = self._extract_modules_from_architecture()

        if isinstance(tests, list) and tests:
            test_modules = []
            for item in tests:
                name = Path(str(item)).name
                if not name.endswith(".py"):
                    name = f"{Path(name).stem}.py"
                if not name.startswith("test_"):
                    name = f"test_{Path(name).stem}.py"
                test_modules.append(name)
            tests = test_modules
        else:
            tests = [f"test_{Path(module).stem}.py" for module in src_modules]

        return {
            "src": list(dict.fromkeys(src_modules)),
            "tests": list(dict.fromkeys(tests)),
        }

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
            path = self.guard.resolve(f"src/{module}")
            if path.exists():
                continue

            skeleton = (
                '"""Module implementation generated from architecture."""\n\n'
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
                "- Do not inject template/example code unrelated to the task context.\n"
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
            if not code:
                code = self.guard.resolve(f"src/{module}").read_text(encoding="utf-8")

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
                    matches = difflib.get_close_matches(module, available, n=1)
                    if not matches:
                        continue
                    replacement = matches[0]
                    content = content.replace(
                        f"from src.{module}",
                        f"from src.{replacement}"
                    )
            for module in _IMPORT_PATTERN.findall(content):
                if module not in available:
                    matches = difflib.get_close_matches(module, available, n=1)
                    if not matches:
                        continue
                    replacement = matches[0]
                    content = content.replace(
                        f"import src.{module}",
                        f"import src.{replacement}"
                    )
            if content != original:
                file_path.write_text(content, encoding="utf-8")
                corrected.append(file_path)
        return corrected

    def validate_source_code(self) -> list[dict[str, str]]:
        src_dir = self.guard.resolve("src")
        issues = validate_source_directory(src_dir)
        self.memory.write_json("source_validation_report.json", issues)
        self.memory.append_devlog(f"Source validation completed with {len(issues)} issue(s)")
        return issues

    def extract_api(self) -> dict:
        src_dir = self.guard.resolve("src")
        api_description = extract_api_from_source(src_dir)
        self.memory.write_json("api_description.json", api_description)
        self.memory.append_devlog("API extraction phase completed")
        return api_description

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

    def _build_fallback_test(self, module: str) -> str:
        stem = Path(module).stem
        return (
            f"def test_{stem}_module_imports():\n"
            f"    __import__('src.{stem}', fromlist=['*'])\n"
        )

    def generate_tests_from_structure(self) -> list[Path]:
        context = self._full_context()
        structure = self._load_file_structure()

        tests_dir = self.guard.resolve("tests")
        tests_dir.mkdir(parents=True, exist_ok=True)

        generated: list[Path] = []

        api_modules: set[str] = set()
        if context["api_description"]:
            try:
                parsed_api = json.loads(context["api_description"])
                modules = parsed_api.get("modules", {})
                if isinstance(modules, dict):
                    api_modules = {f"{name}.py" for name in modules.keys()}
            except json.JSONDecodeError:
                api_modules = set()

        if api_modules:
            target_modules = [module for module in structure["src"] if module in api_modules]
        else:
            target_modules = structure["src"]

        for module in target_modules:
            stem = Path(module).stem
            test_name = f"test_{stem}.py"

            prompt = "\n\n".join(
                [
                    "Project specification:",
                    context["task"],
                    "Architecture:",
                    context["architecture"],
                    "Project file structure:",
                    context["file_structure"],
                    "Extracted API description:",
                    context["api_description"],
                    "Project source code:",
                    self._source_snippets(),
                    "Existing tests:",
                    self._existing_tests(),
                    f"Generate pytest tests for module src/{module} based only on the real API.",
                    "Rules:\n"
                    "- Output test code for exactly one file.\n"
                    f"- The test file must be tests/{test_name}.\n"
                    f"- Tests must only reference src/{module}.\n"
                    "- Do not reference non-existent modules.\n"
                    "- Test only functions/classes/methods that exist in the extracted API.",
                ]
            )

            response = generate(prompt)
            blocks = self._extract_blocks(response)

            valid_code = ""
            for file_hint, block in blocks:
                if file_hint and Path(file_hint).name == test_name:
                    valid_code = block
                    break

            if not valid_code and blocks:
                valid_code = blocks[0][1]

            if not valid_code:
                valid_code = self._build_fallback_test(module)

            test_file = self.guard.resolve(f"tests/{test_name}")
            existing = ""
            if test_file.exists():
                existing = test_file.read_text(encoding="utf-8")
            if existing and valid_code not in existing:
                valid_code = existing + "\n\n" + valid_code
            test_file.write_text(valid_code, encoding="utf-8")
            generated.append(test_file)

        self._update_state()
        self.memory.append_devlog(
            f"Test generation phase completed for {len(target_modules)} module(s)"
        )

        return generated
