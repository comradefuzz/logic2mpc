#!/usr/bin/env python3
"""Сравнение двух адаптеров одного источника: доля функций с одинаковым телом.

    adapter_overlap.py logic2mpc/adapters/logic.py logic2mpc/adapters/logic12.py

Функции (и методы как `Класс.метод`) сравниваются по AST тела без докстрингов и комментариев.
Доля это число одинаковых функций к размеру большего модуля. Правило и порог решения: CLAUDE.md, docs/adapters.md.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def functions(path: Path) -> dict[str, str]:
    """Имя функции и нормализованное тело."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = list(child.body)
                if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                    body = body[1:]
                found[f"{prefix}{child.name}"] = "\n".join(ast.dump(item) for item in body) + "|" + ast.dump(child.args)
                visit(child, f"{prefix}{child.name}.")

    visit(tree, "")
    return found


def compare(first: Path, second: Path) -> dict:
    a, b = functions(first), functions(second)
    both = set(a) & set(b)
    identical = sorted(n for n in both if a[n] == b[n])
    changed = sorted(n for n in both if a[n] != b[n])
    biggest = max(len(a), len(b))
    return {
        "a": str(first), "b": str(second), "total_a": len(a), "total_b": len(b),
        "identical": identical, "changed": changed,
        "only_a": sorted(set(a) - set(b)), "only_b": sorted(set(b) - set(a)),
        "ratio": len(identical) / biggest if biggest else 1.0,
    }


def report(result: dict) -> str:
    lines = [
        f"{result['a']}: {result['total_a']} функций, {result['b']}: {result['total_b']} функций",
        f"одинаковых: {len(result['identical'])}, доля {round(result['ratio'] * 100)}%",
        f"changed ({len(result['changed'])}): {', '.join(result['changed']) or 'нет'}",
        f"только в первом: {', '.join(result['only_a']) or 'нет'}",
        f"только во втором: {', '.join(result['only_b']) or 'нет'}",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    print(report(compare(Path(argv[0]), Path(argv[1]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
