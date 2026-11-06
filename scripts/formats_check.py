#!/usr/bin/env python3
"""Проверка и экспорт базы знаний о форматах docs/formats.

    formats_check.py                     проверить базы и стори
    formats_check.py --export logic|mpc  факты для модели, --all добавляет все статусы
    formats_check.py --requests          открытые реквесты
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASES = {"logic": "LOGIC", "mpc": "MPC"}
FACT_FIELDS = ("status", "applies", "evidence", "fact", "updated")
FACT_STATUSES = ("confirmed", "single-sample", "hypothesis", "refuted", "open")
USABLE_STATUSES = ("confirmed", "single-sample")
REQUEST_FIELDS = (
    "status", "kind", "targets", "proposed-status", "applies", "evidence", "found-in", "created",
)
REQUEST_STATUSES = ("open", "applied", "rejected")
REQUEST_KINDS = ("add", "correct", "close-open")
FIRST_CHECKED_STORY = 7
SKIPPED = ("INDEX.md",)


@dataclass(frozen=True)
class Fact:
    id: str
    path: Path
    block: str
    fields: dict[str, str]


@dataclass(frozen=True)
class Request:
    id: str
    path: Path
    fields: dict[str, str]

    @property
    def targets(self) -> list[str]:
        return [x.strip() for x in self.fields.get("targets", "").split(",") if x.strip()]


def fact_files(base: Path) -> list[Path]:
    return [p for p in sorted(base.glob("*.md")) if p.name not in SKIPPED]


def parse_facts(path: Path) -> list[Fact]:
    text = path.read_text(encoding="utf-8")
    facts = []
    for chunk in re.split(r"(?m)^(?=### )", text):
        match = re.match(r"### (\S+)", chunk)
        if match:
            fields = dict(re.findall(r"(?m)^- ([a-z-]+): ?(.*)$", chunk))
            facts.append(Fact(match.group(1), path, chunk.strip(), fields))
    return facts


def parse_request(path: Path) -> Request:
    match = re.match(r"---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
    fields = dict(re.findall(r"(?m)^([a-z-]+): ?(.*)$", match.group(1))) if match else {}
    return Request(fields.get("id", path.stem), path, fields)


def load_facts(base: Path) -> list[Fact]:
    return [fact for path in fact_files(base) for fact in parse_facts(path)]


def load_requests(base: Path) -> list[Request]:
    return [parse_request(path) for path in sorted((base / "requests").glob("*.md"))]


def repeated(ids: list[str]) -> set[str]:
    return {x for x in ids if ids.count(x) > 1}


def check_facts(prefix: str, facts: list[Fact]) -> list[str]:
    errors = [f"повтор номера {x}" for x in sorted(repeated([f.id for f in facts]))]
    known = {f.id for f in facts}
    for fact in facts:
        where = f"{fact.path.name}: {fact.id}"
        if not re.fullmatch(rf"{prefix}-\d{{3}}", fact.id):
            errors.append(f"{where}: префикс номера не соответствует базе")
        errors += [f"{where}: нет поля {x}" for x in FACT_FIELDS if not fact.fields.get(x)]
        status = fact.fields.get("status")
        if status and status not in FACT_STATUSES:
            errors.append(f"{where}: неизвестный status {status}")
        target = fact.fields.get("superseded-by")
        if target and target not in known:
            errors.append(f"{where}: superseded-by ссылается на {target}, такой записи нет")
    return errors


def check_requests(prefix: str, requests: list[Request], facts: list[Fact]) -> list[str]:
    errors = [f"повтор номера {x}" for x in sorted(repeated([r.id for r in requests]))]
    known = {f.id for f in facts}
    for request in requests:
        where = f"{request.path.name}: {request.id}"
        if not re.fullmatch(rf"{prefix}-R-\d{{3}}", request.id):
            errors.append(f"{where}: префикс номера не соответствует базе")
        if not request.path.name.startswith(f"{request.id}-"):
            errors.append(f"{where}: имя файла не начинается с номера")
        missing = [x for x in REQUEST_FIELDS if x not in request.fields]
        missing += [x for x in REQUEST_FIELDS if x != "targets" and x in request.fields and not request.fields[x]]
        errors += [f"{where}: нет поля {x}" for x in missing]
        fields = request.fields
        if fields.get("status") and fields["status"] not in REQUEST_STATUSES:
            errors.append(f"{where}: неизвестный status {fields['status']}")
        if fields.get("kind") and fields["kind"] not in REQUEST_KINDS:
            errors.append(f"{where}: неизвестный kind {fields['kind']}")
        wanted = fields.get("proposed-status")
        if wanted and wanted not in FACT_STATUSES:
            errors.append(f"{where}: неизвестный proposed-status {wanted}")
        errors += [f"{where}: targets ссылается на {x}, такой записи нет" for x in request.targets if x not in known]
        if fields.get("kind") == "add" and request.targets:
            errors.append(f"{where}: add не может иметь targets")
        if fields.get("kind") in ("correct", "close-open") and not request.targets:
            errors.append(f"{where}: {fields['kind']} требует targets")
    return errors


EXPORT_COLUMNS = ("path", "class", "observed", "required", "export_value", "fact", "note")


def check_export_spec(base: Path, facts: list[Fact]) -> list[str]:
    """Реестр полей для экспорта: пути есть в schema.tsv, факты существуют и пригодны для кода."""
    spec = base / "export.tsv"
    if not spec.is_file():
        return []
    schema = base / "schema.tsv"
    paths = {x.split("\t")[0] for x in schema.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")} if schema.is_file() else set()
    by_id = {f.id: f for f in facts}
    lines = [x for x in spec.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    if not lines or tuple(lines[0].split("\t")) != EXPORT_COLUMNS:
        return ["export.tsv: неверная шапка"]
    errors = []
    for number, line in enumerate(lines[1:], 2):
        cells = (line.split("\t") + [""] * len(EXPORT_COLUMNS))[: len(EXPORT_COLUMNS)]
        where = f"export.tsv:{number}"
        if cells[0] not in paths:
            errors.append(f"{where}: путь {cells[0]} нет в schema.tsv")
        for id_ in (x.strip() for x in cells[5].split(",") if x.strip()):
            status = by_id[id_].fields.get("status") if id_ in by_id else None
            if id_ not in by_id:
                errors.append(f"{where}: факт {id_} не найден")
            elif status not in USABLE_STATUSES:
                errors.append(f"{where}: факт {id_} имеет status {status}, нужен confirmed или single-sample")
    return errors


def check_independence(base: Path, other: str) -> list[str]:
    pattern = re.compile(rf"\b{BASES[other]}-(R-)?\d{{3}}\b|\.\./{other}\b")
    errors = []
    for path in sorted(base.rglob("*.md")):
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            errors.append(f"{path.name}: ссылка на запись другой базы: {match.group(0)}")
    return errors


def check_stories(stories: Path, requests: dict[str, Request]) -> list[str]:
    errors = []
    for path in sorted(stories.glob("S-*.md")):
        number = int(path.name[2:5])
        text = path.read_text(encoding="utf-8")
        status = re.search(r"(?m)^status: (\S+)$", text)
        if number < FIRST_CHECKED_STORY or not status or status.group(1) not in ("acceptance", "done"):
            continue
        story = f"S-{number:03}"
        section = re.search(r"(?ms)^## Реквесты\n(.*?)(?=^## |\Z)", text)
        body = section.group(1).strip() if section else ""
        ids = re.findall(r"\b(?:LOGIC|MPC)-R-\d{3}\b", body)
        if not ids and not body.lower().startswith("нет"):
            errors.append(f"{path.name}: раздел «Реквесты» пуст или отсутствует")
        for id_ in ids:
            if id_ not in requests:
                errors.append(f"{path.name}: реквеста {id_} нет в базе")
            elif story not in requests[id_].fields.get("found-in", ""):
                errors.append(f"{path.name}: в found-in реквеста {id_} нет {story}")
    return errors


def check(formats: Path, stories: Path) -> list[str]:
    errors: list[str] = []
    all_requests: dict[str, Request] = {}
    for name, prefix in BASES.items():
        base = formats / name
        facts = load_facts(base)
        requests = load_requests(base)
        errors += check_facts(prefix, facts)
        errors += check_requests(prefix, requests, facts)
        errors += check_export_spec(base, facts)
        errors += check_independence(base, next(x for x in BASES if x != name))
        all_requests |= {r.id: r for r in requests}
    return errors + check_stories(stories, all_requests)


def export(formats: Path, name: str, everything: bool = False) -> str:
    base = formats / name
    pending: dict[str, list[str]] = {}
    for request in load_requests(base):
        if request.fields.get("status") == "open":
            for target in request.targets:
                pending.setdefault(target, []).append(request.id)
    blocks = []
    for fact in load_facts(base):
        if everything or fact.fields.get("status") in USABLE_STATUSES:
            marks = "".join(f"\n- open-request: {x}" for x in pending.get(fact.id, []))
            blocks.append(fact.block + marks)
    return "\n\n".join(blocks) + "\n"


def open_requests(formats: Path) -> str:
    lines = []
    for name in BASES:
        for request in load_requests(formats / name):
            if request.fields.get("status") == "open":
                lines.append(f"{request.id} {request.fields.get('kind')} {request.path.relative_to(formats)}")
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", choices=BASES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--requests", action="store_true")
    args = parser.parse_args()
    formats = ROOT / "docs" / "formats"
    if args.export:
        sys.stdout.write(export(formats, args.export, args.all))
        return 0
    if args.requests:
        sys.stdout.write(open_requests(formats))
        return 0
    errors = check(formats, ROOT / "stories")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
