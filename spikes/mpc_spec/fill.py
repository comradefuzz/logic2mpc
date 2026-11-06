#!/usr/bin/env python3
"""Заполняет export.tsv по результатам спайка 9 и пишет список переменных полей с предложением значения.

    fill.py            обновляет docs/formats/mpc/export.tsv

Колонка `required`: yes, no, unknown. no значит, что поле можно не писать (кейс спайка убирал его, Live 2 открыл
проект). Каждое no и yes ссылается на факт. Переменные поля (несколько значений в образцах) и всё не проверенное
остаются unknown, но получают значение из `Empty.xpj` (факт MPC-110), из плана или фиксированное. Значение с пометкой `decision` в колонке note это решение, а не наблюдение.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "mpc_build"))
import cases  # noqa: E402
import cases2  # noqa: E402
import registry  # noqa: E402

CLIP = cases.CLIP
INSTRUMENT = "data.tracks[].program.drum.instruments[]"
EVENT = f"data.{CLIP}.eventList.events[]"
# Блок: (поля, которые убирал кейс, факт). Поля None значит все постоянные поля блока верхнего уровня.
TESTED: dict[str, tuple[set[str] | None, str]] = {
    "data.tracks[]": (None, "MPC-114,MPC-116"),
    "data.tracks[].program": (None, "MPC-114,MPC-116"),
    "data.tracks[].program.midi": (None, "MPC-116"),
    INSTRUMENT: (None, "MPC-117"),
    f"{INSTRUMENT}.layersv[]": (set(cases2.LAYER_REST) | {"version"}, "MPC-117"),
    f"data.{CLIP}": (None, "MPC-116"),
    EVENT: (None, "MPC-118"),
    f"{EVENT}.note": (set(cases2.NOTE_REST) | set(cases2.MODIFIERS) | {"version"}, "MPC-118"),
    "data.samples[]": (None, "MPC-116"),
    "data.sequences[].value": (None, "MPC-116"),
}
LENGTHS = {
    "data.sequences[].value.loopEndBar", "data.sequences[].value.loopEndPulses",
    "data.sequences[].value.trackClipMaps[][].value.loopEndPulses",
}
REQUIRED = {f"{INSTRUMENT}.version": "MPC-117", f"{EVENT}.version": "MPC-118"}


def parent_and_leaf(path: str) -> tuple[str, str]:
    parent, _, name = path.rpartition(".")
    return parent, name


def decide(row: dict[str, str]) -> tuple[str, str, str]:
    """Возвращает required, export_value, fact."""
    path, kind = row["path"], row["class"]
    parts = path.split(".")
    if len(parts) >= 2 and parts[1].removesuffix("[]") not in cases.ROOT_KEEP:
        return "no", "", "MPC-113"
    if path in LENGTHS:
        return "unknown", "из плана: равно длине секции (MPC-035)", ""
    if path in REQUIRED:
        return "yes", row["observed"], REQUIRED[path]
    if kind == "const":
        parent, name = parent_and_leaf(path)
        if parent in TESTED:
            fields, fact = TESTED[parent]
            if fields is None or name in fields:
                return "no", "", fact
    if kind == "ref":
        return "unknown", "из плана", ""
    return "unknown", "", ""


def lookup(node: Any, parts: list[str]) -> list[Any]:
    if not parts:
        return [node]
    head, rest = parts[0], parts[1:]
    many = head.endswith("[]")
    key = head.removesuffix("[]")
    if key == "*":
        found = []
        for child in node.values() if isinstance(node, dict) else []:
            found += lookup(child, rest)
        return found
    if not isinstance(node, dict) or key not in node:
        return []
    child = node[key]
    if many:
        found = []
        for item in child if isinstance(child, list) else []:
            if isinstance(item, list):
                for sub in item:
                    found += lookup(sub, rest)
            else:
                found += lookup(item, rest)
        return found
    return lookup(child, rest)


def template_values(data: dict[str, Any], path: str) -> list[str]:
    parts = path.removeprefix("data.").split(".")
    seen: list[str] = []
    for value in lookup(data, parts):
        text = str(value)
        if text not in seen:
            seen.append(text)
    return seen


EV = "sequences[].value.trackClipMaps[][].value.eventList.events[]"
PLAN = {
    "masterTempo", "sequences[].value.bpm", "sequences[].value.lengthBars", "sequences[].value.lengthPulses",
    "sequences[].value.trackClipMaps[][].value.endPulses", f"{EV}.time", f"{EV}.note.note", f"{EV}.note.velocity",
    f"{EV}.note.length", "tracks[].colour", "samples[].metadata.tempo", "tracks[].program.samples[].metadata.tempo",
    "tracks[].program.drum.instruments[].tempo", "sequences[].value.timeSignatureTrack.timeSignatures[].barStart",
    "sequences[].value.timeSignatureTrack.timeSignatures[].beatsPerBar",
}
FIXED = {
    **{path: "по умолчанию, как в D01: шесть пустых локаторов (позиция -1, имя пустое)" for path in (
        "sequences[].value.locators.colours[]", "sequences[].value.locators.names[]",
        "sequences[].value.locators.positions[].bar", "sequences[].value.locators.positions[].beat",
        "sequences[].value.locators.positions[].pulse",
    )},
    **{path: "не пишется: экспорт не создаёт" for path in (
        f"{EV}.automation.note", f"{EV}.automation.value",
        "sequences[].value.trackClipMaps[][].value.perClipParameterValues.perClipParameterValues[].key.instrumentIndex",
        "sequences[].value.trackClipMaps[][].value.perClipParameterValues.perClipParameterValues[].value",
    )},
    "samples[].metadata.rootNote": "`60`, решение: значение образцов, не проверялось",
    "samples[].loadImpl": "`0`, решение: как в D01, не проверялось",
    "sequences[].value.autoSelectTrackIndex": "`-1`, решение: как в D01, не проверялось",
    f"{EV}.channel": "`0`, решение: как в D01, не проверялось",
    "samples[].metadata.key": "`C Major`, решение: в плане тональности нет",
    "tracks[].program.samples[].metadata.key": "`C Major`, решение: в плане тональности нет",
    f"{EV}.type": "`3` (нота, MPC-034)", f"{EV}.muted": "`False`", f"{EV}.invented": "`False`",
    "tracks[].program.type": "`0` драм-трек, `4` MIDI-трек, по способу экспорта",
    "tracks[].recordArm": "`True` только у текущего трека, у остальных `False` (MPC-111)",
    "tracks[].program.drum.instruments[].triggerMode": "по плану: `0` ваншот, `2` Note On (MPC-115)",
    "tracks[].program.drum.instruments[].monophonic": "по плану (MPC-115)",
    "tracks[].program.drum.instruments[].polyphony": "по плану (MPC-115)",
    "tracks[].program.drum.instruments[].whichMuteGroup": "по плану (MPC-115)",
    "tracks[].program.drum.instruments[].warpEnable": "`False` (MPC-115)",
}


def empty_drum_project() -> dict[str, Any]:
    """Empty.xpj без служебных треков: образец значений для экспортируемых полей."""
    data = cases.patch.load(cases.PROJECTS / cases.EMPTY).data
    data["tracks"] = [t for t in data["tracks"] if t["program"]["type"] == 0]
    return data


def proposal(row: dict[str, str], empty: dict[str, Any]) -> tuple[str, str]:
    """Возвращает значение и источник: fixed, plan, empty или open."""
    short = row["path"].removeprefix("data.")
    if short in FIXED:
        return FIXED[short], "fixed"
    if short in PLAN:
        return "из плана", "plan"
    found = template_values(empty, row["path"])
    if len(found) == 1:
        return found[0], "empty"
    if len(found) > 1:
        return f"как в Empty, по пэду или элементу ({len(found)} значений)", "empty-many"
    created = ("samples[]", "sequences[]")
    parent = row["path"].rpartition(".")[0]
    if not short.startswith(created + ("tracks[].program.samples[]", "tracks[].program.midi")) and not found and parent and not template_values(empty, parent):
        return "не пишется: объекта нет в Empty", "absent"
    return "", "open"


def variables_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Открытые переменные поля",
        "",
        "Поля с несколькими значениями в образцах, которым не нашлось решения: их нет в `Empty.xpj` и экспорт не вычисляет их из плана. Остальные переменные поля закрыты значением из `Empty.xpj` (`export_value`, факт MPC-110) или правилом (из плана, фиксированное значение). Принятое решение вносится в `export.tsv`.",
        "",
        "| Поле | Наблюдавшиеся |",
        "|---|---|",
    ]
    for row in rows:
        if row["class"] == "var" and row["fact"] == "" and row["export_value"] == "":
            observed = row["observed"].replace("|", ", ")
            short = observed if len(observed) <= 70 else observed[:67] + "..."
            lines.append(f"| `{row['path'].removeprefix('data.')}` | {short} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    target = registry.MPC / "export.tsv"
    rows = registry.read(target.read_text(encoding="utf-8"))
    empty = empty_drum_project()
    for row in rows:
        row["required"], row["export_value"], row["fact"] = decide(row)
        if row["required"] == "unknown" and row["class"] in ("const", "var") and not row["export_value"]:
            value, source = proposal(row, empty)
            if source == "empty":
                row["export_value"], row["fact"] = value, "MPC-110"
            elif source in ("fixed", "plan", "absent", "empty-many"):
                row["export_value"], row["note"] = value, "decision"
    target.write_text(registry.render(rows), encoding="utf-8")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["required"]] = counts.get(row["required"], 0) + 1
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
