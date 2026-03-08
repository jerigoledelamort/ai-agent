from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from pathlib import Path
import builtins


@dataclass
class ValidationIssue:
    file: str
    error_type: str
    message: str


class _ModuleNameValidator(ast.NodeVisitor):
    """Lightweight static checker for undefined top-level names."""

    def __init__(self) -> None:
        self.defined: set[str] = set()
        self.used: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defined.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.defined.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defined.add(node.name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.defined.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            self.defined.add(alias.asname or alias.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.defined.add(node.target.id)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.used.append((node.id, node.lineno))


def _check_missing_names(tree: ast.AST, file_path: Path) -> list[ValidationIssue]:
    visitor = _ModuleNameValidator()
    visitor.visit(tree)

    known = set(dir(builtins)) | visitor.defined
    issues: list[ValidationIssue] = []
    for name, line in visitor.used:
        if name in known:
            continue
        issues.append(
            ValidationIssue(
                file=str(file_path),
                error_type="NameError",
                message=f"Undefined name '{name}' at line {line}",
            )
        )
    return issues



def _check_local_imports(tree: ast.AST, file_path: Path, available_modules: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
            module_name = node.module.split(".", 1)[1]
            if module_name not in available_modules:
                issues.append(
                    ValidationIssue(
                        file=str(file_path),
                        error_type="ImportError",
                        message=f"Cannot import src.{module_name}",
                    )
                )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    module_name = alias.name.split(".", 1)[1]
                    if module_name not in available_modules:
                        issues.append(
                            ValidationIssue(
                                file=str(file_path),
                                error_type="ImportError",
                                message=f"Cannot import src.{module_name}",
                            )
                        )
    return issues

def validate_source_directory(src_dir: Path) -> list[dict[str, str]]:
    issues: list[ValidationIssue] = []

    if not src_dir.exists():
        return []

    available_modules = {path.stem for path in src_dir.glob("*.py") if path.name != "__init__.py"}

    for file_path in sorted(src_dir.glob("*.py")):
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(file_path))
            compile(source, str(file_path), "exec")
        except SyntaxError as exc:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    error_type="SyntaxError",
                    message=str(exc),
                )
            )
            continue

        issues.extend(_check_local_imports(tree, file_path, available_modules))

        try:
            issues.extend(_check_missing_names(tree, file_path))
        except Exception as exc:  # defensive: validator must never stop pipeline
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    error_type="ImportError",
                    message=f"Validator failed: {exc}",
                )
            )

    return [asdict(item) for item in issues]
