from __future__ import annotations

import ast
from pathlib import Path


def _format_arg(arg: ast.arg, default: str | None = None) -> str:
    if default is None:
        return arg.arg
    return f"{arg.arg}={default}"


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts: list[str] = []

    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
    for arg, default in zip(positional, defaults):
        rendered_default = ast.unparse(default) if default is not None else None
        parts.append(_format_arg(arg, rendered_default))

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")

    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        rendered_default = ast.unparse(default) if default is not None else None
        parts.append(_format_arg(arg, rendered_default))

    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return f"{node.name}({', '.join(parts)})"


def _function_payload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str | bool]:
    return {
        "name": node.name,
        "signature": _signature(node),
        "is_public": not node.name.startswith("_"),
        "is_async": isinstance(node, ast.AsyncFunctionDef),
    }


def extract_api_from_source(src_dir: Path) -> dict:
    modules: dict[str, dict] = {}

    if not src_dir.exists():
        return {"modules": modules}

    for file_path in sorted(src_dir.glob("*.py")):
        if file_path.name == "__init__.py":
            continue

        module_name = file_path.stem
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

        module_data = {
            "classes": {},
            "functions": [],
        }

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module_data["functions"].append(_function_payload(node))
            elif isinstance(node, ast.ClassDef):
                methods = []
                public_methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method = _function_payload(item)
                        methods.append(method)
                        if method["is_public"]:
                            public_methods.append(method["name"])
                module_data["classes"][node.name] = {
                    "methods": methods,
                    "public_methods": public_methods,
                }

        modules[module_name] = module_data

    return {"modules": modules}
