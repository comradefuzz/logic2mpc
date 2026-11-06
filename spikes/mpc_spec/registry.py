#!/usr/bin/env python3
"""Реестр полей для экспорта: `schema.tsv` → `docs/formats/mpc/export.tsv`.

    registry.py            печатает реестр в stdout
    registry.py --write    создаёт export.tsv, а если он есть, обновляет классы и значения, не трогая заполненное
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

MPC = Path(__file__).resolve().parents[2] / "docs" / "formats" / "mpc"
COLUMNS = ("path", "class", "observed", "required", "export_value", "fact", "note")
REF_LEAVES = {"name", "sampleName", "sampleFile", "path", "key"}
OPTIONAL_LEAVES = {"volume", "volumeKnown", "pan", "panKnown"}
EXPORT_PROGRAMS = {0, 4}
DESCRIPTION = re.compile(
    r"^(?P<kinds>[\w|]+)(?: \[(?P<span>[^\]]*)\])?(?: \{(?P<values>.*)\}| \((?P<many>\d+) значений\))?$"
)


@dataclass(frozen=True)
class Row:
    path: str
    count: int
    kinds: set[str]
    values: list[str] | None
    programs: set[int]
    distinct: int | None = None


def parse_schema(text: str) -> list[Row]:
    rows = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        path, count, description, *rest = (line.split("\t") + ["", "", "", ""])[:4]
        match = DESCRIPTION.match(description)
        if not match:
            raise ValueError(f"не разобрана строка схемы: {line[:80]}")
        many = match["many"]
        values = None if many else (match["values"].split(", ") if match["values"] else [])
        programs = {int(x) for x in rest[0].split(",") if x}
        rows.append(Row(path, int(count), set(match["kinds"].split("|")), values, programs, int(many) if many else None))
    return rows


def leaf(path: str) -> str:
    return path.rsplit(".", 1)[-1].removesuffix("[]")


def classify(row: Row) -> str:
    if row.kinds <= {"dict", "list"}:
        return "node"
    if leaf(row.path) in REF_LEAVES:
        return "ref"
    return "const" if row.values is not None and len(row.values) == 1 else "var"


def in_scope(row: Row) -> bool:
    """Объекты, которые создаёт экспорт: драм- и MIDI-треки, секвенции, сэмплы и верхний уровень проекта."""
    path = row.path
    if path.count(".") == 1:
        return True
    if path == "data.tracks[]" or path.startswith("data.tracks[]."):
        return not row.programs or bool(row.programs & EXPORT_PROGRAMS)
    return path.startswith(("data.sequences[]", "data.samples[]"))


def build_rows(schema: str) -> list[dict[str, str]]:
    table = []
    for row in parse_schema(schema):
        if not in_scope(row):
            continue
        observed = f"({row.distinct} значений)" if row.values is None else "|".join(row.values)
        table.append({
            "path": row.path, "class": classify(row), "observed": observed, "required": "unknown",
            "export_value": "", "fact": "", "note": "optional-export" if leaf(row.path) in OPTIONAL_LEAVES else "",
        })
    return sorted(table, key=lambda r: r["path"])


def render(rows: list[dict[str, str]]) -> str:
    lines = ["\t".join(COLUMNS)] + ["\t".join(row[c] for c in COLUMNS) for row in rows]
    return "\n".join(lines) + "\n"


def read(text: str) -> list[dict[str, str]]:
    lines = [x for x in text.splitlines() if x and not x.startswith("#")]
    if tuple(lines[0].split("\t")) != COLUMNS:
        raise ValueError("неверная шапка export.tsv")
    return [dict(zip(COLUMNS, (line.split("\t") + [""] * len(COLUMNS))[: len(COLUMNS)])) for line in lines[1:]]


def merge(old: list[dict[str, str]], fresh: list[dict[str, str]]) -> list[dict[str, str]]:
    """Класс и наблюдавшиеся значения обновляются, остальные колонки остаются как их заполнили."""
    known = {r["path"]: r for r in old}
    for row in fresh:
        if row["path"] in known:
            known[row["path"]].update({"class": row["class"], "observed": row["observed"]})
        else:
            known[row["path"]] = row
    return sorted(known.values(), key=lambda r: r["path"])


def main() -> int:
    fresh = build_rows((MPC / "schema.tsv").read_text(encoding="utf-8"))
    if "--write" not in sys.argv[1:]:
        sys.stdout.write(render(fresh))
        return 0
    target = MPC / "export.tsv"
    rows = merge(read(target.read_text(encoding="utf-8")), fresh) if target.is_file() else fresh
    target.write_text(render(rows), encoding="utf-8")
    print(f"{target.relative_to(MPC.parents[2])}: {len(rows)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
