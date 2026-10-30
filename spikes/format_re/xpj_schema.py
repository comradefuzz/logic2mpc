#!/usr/bin/env python3
"""Перепись схемы JSON всех .xpj и .xpm из test-projects/mpc. Только чтение.

    xpj_schema.py            схема: путь, частота, значения, типы программ
    xpj_schema.py --routes F  маршрут и Mute по трекам файла F
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "test-projects" / "mpc"
LIMIT = 12


def load(path: Path) -> tuple[list[str], object]:
    raw = gzip.decompress(path.read_bytes())
    offset = 0
    header = []
    for _ in range(5):
        end = raw.index(b"\n", offset)
        header.append(raw[offset:end].decode())
        offset = end + 1
    return header, json.loads(raw[offset:])["data"]


class Field:
    def __init__(self) -> None:
        self.count = 0
        self.types: Counter[str] = Counter()
        self.values: Counter[str] = Counter()
        self.low: float | None = None
        self.high: float | None = None
        self.programs: set[int] = set()

    def add(self, value: object) -> None:
        self.count += 1
        self.types[type(value).__name__] += 1
        if isinstance(value, (bool, str)) or value is None:
            self.values[repr(value)[:40]] += 1
        elif isinstance(value, (int, float)):
            self.values[repr(value)[:40]] += 1
            self.low = value if self.low is None else min(self.low, value)
            self.high = value if self.high is None else max(self.high, value)

    def describe(self) -> str:
        kinds = "|".join(sorted(self.types))
        span = ""
        if self.low is not None:
            span = f" [{self.low} .. {self.high}]"
        distinct = len(self.values)
        if not distinct:
            return kinds
        if distinct <= LIMIT:
            shown = ", ".join(x for x, _ in self.values.most_common())
            return f"{kinds}{span} {{{shown}}}"
        return f"{kinds}{span} ({distinct} значений)"


def normal(key: str) -> str:
    """Ключи-номера и идентификаторы сворачиваются в один элемент схемы."""
    return "*" if re.fullmatch(r"-?\d+|value\d+", key) else key


def visit(node: object, path: str, fields: dict[str, Field], program: int | None = None) -> None:
    fields[path].add(node)
    if program is not None:
        fields[path].programs.add(program)
    if isinstance(node, dict):
        if path == "data.tracks[].program":
            program = node["type"]
        for key, value in node.items():
            visit(value, f"{path}.{normal(key)}", fields, program)
    elif isinstance(node, list):
        for value in node:
            visit(value, f"{path}[]", fields, program)


def collect() -> tuple[dict[str, Field], Counter[str], int]:
    fields: dict[str, Field] = defaultdict(Field)
    headers: Counter[str] = Counter()
    paths = sorted(p for p in ROOT.rglob("*") if p.suffix in (".xpj", ".xpm") and p.is_file())
    for path in paths:
        header, data = load(path)
        headers[" / ".join(header)] += 1
        visit(data, "data", fields)
    return fields, headers, len(paths)


def routes(path: Path) -> None:
    _, data = load(path)
    for track in data["tracks"]:
        mixable = track["program"]["mixable"]
        route = mixable["audioRoute"]
        print(track["name"], track["program"]["type"], route["destination"], route["audioRouteSubIndex"],
              route["channelBitmap"]["data"], track["mute"], mixable["mute"], sep="\t")


def main() -> None:
    if sys.argv[1:2] == ["--routes"]:
        routes(ROOT / sys.argv[2])
        return
    fields, headers, total = collect()
    print(f"# файлов {total}, путей {len(fields)}")
    for header, count in headers.most_common():
        print(f"# {count} × {header}")
    for path in sorted(fields):
        kinds = ",".join(str(x) for x in sorted(fields[path].programs))
        print(f"{path}\t{fields[path].count}\t{fields[path].describe()}\t{kinds}")


if __name__ == "__main__":
    main()
