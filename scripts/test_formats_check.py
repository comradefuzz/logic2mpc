"""Проверка базы знаний о форматах на синтетических файлах."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import formats_check  # noqa: E402

FACT = """### {id} Название
- status: {status}
- applies: firmware 3.10
- evidence: S-006
- fact: Текст.
- updated: 2026-10-30
"""

REQUEST = """---
id: {id}
status: {status}
kind: {kind}
targets: {targets}
proposed-status: confirmed
applies: firmware 3.10
evidence: файл с Live 2
found-in: {found}
created: 2026-10-30
---

Что найдено.
"""

STORY = """---
id: {id}
title: T
type: feature
status: {status}
---

{section}
"""


def fact(id_: str = "MPC-001", status: str = "confirmed") -> str:
    return FACT.format(id=id_, status=status)


def request(id_: str = "MPC-R-001", status: str = "open", kind: str = "correct",
            targets: str = "MPC-001", found: str = "S-007") -> str:
    return REQUEST.format(id=id_, status=status, kind=kind, targets=targets, found=found)


def errors(files: dict[str, str]) -> list[str]:
    """Собирает дерево docs/formats и stories и возвращает ошибки проверки."""
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        (root / "formats" / "logic" / "requests").mkdir(parents=True)
        (root / "formats" / "mpc" / "requests").mkdir(parents=True)
        (root / "stories").mkdir()
        for path, text in files.items():
            (root / path).write_text(text, encoding="utf-8")
        return formats_check.check(root / "formats", root / "stories")


def test_good_fact_and_request_pass() -> None:
    assert errors({
        "formats/mpc/a.md": fact(),
        "formats/mpc/requests/MPC-R-001-x.md": request(),
    }) == []


def test_fact_requires_each_field() -> None:
    for field in formats_check.FACT_FIELDS:
        text = "".join(x for x in fact().splitlines(True) if not x.startswith(f"- {field}:"))
        assert any(field in e for e in errors({"formats/mpc/a.md": text})), field


def test_unknown_status() -> None:
    assert any("status" in e for e in errors({"formats/mpc/a.md": fact(status="maybe")}))


def test_repeated_number_across_files() -> None:
    result = errors({"formats/mpc/a.md": fact(), "formats/mpc/b.md": fact()})
    assert any("повтор" in e for e in result)


def test_foreign_prefix() -> None:
    assert any("префикс" in e for e in errors({"formats/mpc/a.md": fact("LOGIC-001")}))


def test_superseded_by_must_exist() -> None:
    text = fact(status="refuted") + "- superseded-by: MPC-009\n"
    assert any("MPC-009" in e for e in errors({"formats/mpc/a.md": text}))
    good = text.replace("MPC-009", "MPC-002") + "\n" + fact("MPC-002")
    assert errors({"formats/mpc/a.md": good}) == []


def test_bases_do_not_mention_each_other() -> None:
    assert any("другой базы" in e for e in errors({
        "formats/mpc/a.md": fact() + "\nСм. LOGIC-001\n",
        "formats/logic/a.md": fact("LOGIC-001"),
    }))
    assert any("другой базы" in e for e in errors({
        "formats/logic/a.md": fact("LOGIC-001") + "\nСм. ../mpc/a.md\n",
    }))
    assert any("другой базы" in e for e in errors({
        "formats/mpc/a.md": fact(),
        "formats/mpc/requests/MPC-R-001-x.md": request() + "\nСм. LOGIC-R-001\n",
    }))


def test_request_requires_each_field() -> None:
    for field in formats_check.REQUEST_FIELDS:
        text = "".join(x for x in request().splitlines(True) if not x.startswith(f"{field}:"))
        assert any(field in e for e in errors({
            "formats/mpc/a.md": fact(),
            "formats/mpc/requests/MPC-R-001-x.md": text,
        })), field


def test_request_bad_values() -> None:
    base = {"formats/mpc/a.md": fact()}
    path = "formats/mpc/requests/MPC-R-001-x.md"
    assert any("status" in e for e in errors(base | {path: request(status="done")}))
    assert any("kind" in e for e in errors(base | {path: request(kind="move")}))
    assert any("MPC-009" in e for e in errors(base | {path: request(targets="MPC-009")}))
    assert any("add" in e for e in errors(base | {path: request(kind="add")}))
    assert any("correct" in e for e in errors(base | {path: request(targets="")}))
    assert errors(base | {path: request(kind="add", targets="")}) == []


def test_request_repeated_number_and_prefix() -> None:
    base = {"formats/mpc/a.md": fact()}
    assert any("повтор" in e for e in errors(base | {
        "formats/mpc/requests/MPC-R-001-x.md": request(),
        "formats/mpc/requests/MPC-R-001-y.md": request(),
    }))
    assert any("префикс" in e for e in errors(base | {
        "formats/mpc/requests/LOGIC-R-001-x.md": request("LOGIC-R-001"),
    }))


def story(number: int, section: str, status: str = "acceptance") -> dict[str, str]:
    return {f"stories/S-{number:03}-x.md": STORY.format(id=f"S-{number:03}", status=status, section=section)}


def test_story_needs_section() -> None:
    assert any("Реквесты" in e for e in errors(story(8, "## Анализ\n\nТекст.")))
    assert any("Реквесты" in e for e in errors(story(8, "## Реквесты\n\n## Тесты\n", "done")))


def test_story_none_passes() -> None:
    assert errors(story(8, "## Реквесты\n\nНет.")) == []


def test_story_unknown_request() -> None:
    assert any("MPC-R-001" in e for e in errors(story(8, "## Реквесты\n\nMPC-R-001")))


def test_story_request_found_elsewhere() -> None:
    files = {
        "formats/mpc/a.md": fact(),
        "formats/mpc/requests/MPC-R-001-x.md": request(found="S-009"),
    }
    assert any("found-in" in e for e in errors(files | story(8, "## Реквесты\n\nMPC-R-001")))
    files["formats/mpc/requests/MPC-R-001-x.md"] = request(found="S-008")
    assert errors(files | story(8, "## Реквесты\n\nMPC-R-001")) == []


def test_story_skips_old_and_unfinished() -> None:
    assert errors(story(6, "## Анализ")) == []
    assert errors(story(8, "## Анализ", "dev")) == []


def make_base(root: Path) -> None:
    (root / "mpc" / "requests").mkdir(parents=True)
    (root / "logic" / "requests").mkdir(parents=True)
    (root / "mpc" / "a.md").write_text(
        fact("MPC-001") + "\n" + fact("MPC-002", "single-sample") + "\n"
        + fact("MPC-003", "hypothesis") + "\n" + fact("MPC-004", "refuted") + "\n"
        + fact("MPC-005", "open"), encoding="utf-8")
    (root / "mpc" / "requests" / "MPC-R-001-x.md").write_text(request(), encoding="utf-8")
    (root / "mpc" / "requests" / "MPC-R-002-y.md").write_text(
        request("MPC-R-002", status="applied", targets="MPC-002"), encoding="utf-8")


def test_export_filters_status() -> None:
    with tempfile.TemporaryDirectory() as name:
        make_base(Path(name))
        text = formats_check.export(Path(name), "mpc")
        assert "MPC-001" in text and "MPC-002" in text
        assert "MPC-003" not in text and "MPC-004" not in text and "MPC-005" not in text
        full = formats_check.export(Path(name), "mpc", everything=True)
        assert all(f"MPC-00{n}" in full for n in range(1, 6))
        assert "status: refuted" in full


def test_export_marks_open_request() -> None:
    with tempfile.TemporaryDirectory() as name:
        make_base(Path(name))
        text = formats_check.export(Path(name), "mpc")
        first, second = text.split("### MPC-002")
        assert "open-request: MPC-R-001" in first
        assert "open-request" not in second


def test_open_requests_only() -> None:
    with tempfile.TemporaryDirectory() as name:
        make_base(Path(name))
        text = formats_check.open_requests(Path(name))
        assert "MPC-R-001" in text
        assert "MPC-R-002" not in text


def test_real_base_passes() -> None:
    assert formats_check.check(ROOT / "docs" / "formats", ROOT / "stories") == []


EXPORT = "path\tclass\tobserved\trequired\texport_value\tfact\tnote\n"
SCHEMA = "# файлов 1\ndata\t1\tdict\t\ndata.name\t1\tstr (1 значений)\t\n"


def export_row(path: str = "data.name", fact_id: str = "") -> str:
    return f"{path}\tref\t\tunknown\t\t{fact_id}\t\n"


def export_errors(row: str, fact_text: str = "") -> list[str]:
    files = {"formats/mpc/schema.tsv": SCHEMA, "formats/mpc/export.tsv": EXPORT + row}
    if fact_text:
        files["formats/mpc/a.md"] = fact_text
    return errors(files)


def test_export_spec_good_row_and_empty_fact_pass() -> None:
    assert export_errors(export_row()) == []
    assert export_errors(export_row(fact_id="MPC-001"), fact()) == []


def test_export_spec_path_outside_schema() -> None:
    assert any("data.other" in e for e in export_errors(export_row("data.other")))


def test_export_spec_fact_must_exist() -> None:
    assert any("MPC-009" in e for e in export_errors(export_row(fact_id="MPC-009"), fact()))


def test_export_spec_fact_must_be_usable() -> None:
    result = export_errors(export_row(fact_id="MPC-001"), fact(status="hypothesis"))
    assert any("MPC-001" in e and "hypothesis" in e for e in result)


def test_export_spec_several_facts_are_checked() -> None:
    both = fact("MPC-001") + "\n" + fact("MPC-002", "refuted")
    assert any("MPC-002" in e for e in export_errors(export_row(fact_id="MPC-001, MPC-002"), both))


def test_no_export_spec_is_fine() -> None:
    assert errors({"formats/mpc/schema.tsv": SCHEMA}) == []
