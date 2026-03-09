from __future__ import annotations

import ast
from pathlib import Path

from .sandbox_guard import SandboxGuard


def _module_name_from_path(src_dir: Path, file_path: Path) -> str:
    rel = file_path.relative_to(src_dir).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else file_path.stem


def _extract_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return sorted(dict.fromkeys(imports))


def analyze_project(guard: SandboxGuard, src_relative: str = "src") -> dict[str, dict]:
    src_dir = guard.resolve(src_relative)
    modules: dict[str, dict[str, list[str]]] = {}
    dependency_graph: dict[str, list[str]] = {}

    if not src_dir.exists():
        return {"modules": modules}

    for file_path in sorted(src_dir.rglob("*.py")):
        module_name = _module_name_from_path(src_dir, file_path)
        code = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(code)
        except SyntaxError:
            modules[module_name] = {
                "imports": [],
                "classes": [],
                "functions": [],
                "parse_error": ["SyntaxError"],
            }
            dependency_graph[module_name] = []
            continue

        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        imports = _extract_imports(tree)

        modules[module_name] = {
            "imports": imports,
            "classes": classes,
            "functions": functions,
        }

    module_names = set(modules.keys())
    for module_name, details in modules.items():
        deps = []
        for imported in details.get("imports", []):
            if imported in module_names:
                deps.append(imported)
                continue
            imported_root = imported.split(".", 1)[0]
            for candidate in module_names:
                if candidate == imported_root or candidate.startswith(imported_root + "."):
                    deps.append(candidate)
        dependency_graph[module_name] = sorted(dict.fromkeys(deps))

    return {"modules": modules, "dependency_graph": dependency_graph}
