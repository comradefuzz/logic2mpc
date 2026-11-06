#!/usr/bin/env python3
"""Кейсы спайка 9: проекты MPC из реальных образцов с одним изменением на кейс.

    cases.py             пишет проекты в test-projects/mpc/spike9 и обновляет CHECKLIST.md
    cases.py --checklist только CHECKLIST.md

Постоянные поля берутся из реестра по `schema.tsv`. Кейс ничего не собирает для продукта: он удаляет или меняет
поля готового проекта, чтобы Live 2 показал, что обязательно.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "mpc_build"))
import patch  # noqa: E402
import registry  # noqa: E402

PROJECTS = HERE.parents[1] / "test-projects"
OUT = PROJECTS / "mpc" / "spike9"
MAX_CASES = 25
ROOT_KEEP = (
    "version", "key", "masterTempoEnabled", "masterTempo", "samples", "tracks", "sequences",
    "currentTrackIndex", "currentSequence", "engineMode",
)
ASSIGN = ("assignable", "qlink", "rowLaunch", "midiLearn", "parameterSnapshotter")
GUI = ("gui", "tui", "mpcClipMatrixView", "horizontalClipMatrixView", "sharedClipMatrixData")
EMPTY = "reference/Empty.xpj"
PADS = "mpc/spike7/D01 pads16.xpj"
MIDI = "mpc/spike7/M01 midi.xpj"
CLIP = "sequences[].value.trackClipMaps[][].value"
FLIPPED = {0: 2, 2: 0}

Mutation = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class Case:
    id: str
    slug: str
    base: str
    text: str
    touches: tuple[str, ...]
    mutate: Mutation


def changed_paths(before: Any, after: Any, path: str = "") -> set[str]:
    """Пути, где два дерева различаются: значение, добавленный или удалённый ключ и элемент."""
    if isinstance(before, dict) and isinstance(after, dict):
        found: set[str] = set()
        for key in before.keys() | after.keys():
            where = f"{path}.{key}" if path else key
            if key in before and key in after:
                found |= changed_paths(before[key], after[key], where)
            else:
                found.add(where)
        return found
    if isinstance(before, list) and isinstance(after, list):
        found = {f"{path}[{i}]" for i in range(min(len(before), len(after)), max(len(before), len(after)))}
        for i, (a, b) in enumerate(zip(before, after)):
            found |= changed_paths(a, b, f"{path}[{i}]")
        return found
    return set() if before == after and type(before) is type(after) else {path}


def drop_types(*kinds: int) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        data["tracks"] = [t for t in data["tracks"] if t["program"]["type"] not in kinds]
    return run


def drop_keys(*prefixes: str) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        for key in [k for k in data if k.startswith(prefixes)]:
            del data[key]
    return run


def keep_root(data: dict[str, Any]) -> None:
    for key in [k for k in data if k not in ROOT_KEEP]:
        del data[key]


def drop_consts(node: dict[str, Any], prefix: str, consts: set[str]) -> None:
    for key in [k for k in node if f"{prefix}.{k}" in consts]:
        del node[key]


def tracks_of(data: dict[str, Any], kind: int) -> list[dict[str, Any]]:
    return [t for t in data["tracks"] if t["program"]["type"] == kind]


def filled_pads(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for t in tracks_of(data, 0) for i in t["program"]["drum"]["instruments"] if i["layersv"][0]["sampleFile"]]


def clips(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [c["value"] for s in data["sequences"] for row in s["value"]["trackClipMaps"] for c in row]


def events(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for c in clips(data) for e in c["eventList"]["events"]]


def set_pads(**fields: Any) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        for pad in filled_pads(data):
            pad.update(fields)
    return run


def flip_trigger(data: dict[str, Any]) -> None:
    for pad in filled_pads(data):
        pad["triggerMode"] = FLIPPED.get(pad["triggerMode"], 0)


def mute_group(data: dict[str, Any]) -> None:
    for pad in filled_pads(data)[:2]:
        pad["whichMuteGroup"] = 1


def minimal(consts: set[str]) -> dict[str, Mutation]:
    def tracks(kind: int, *prefixes: str) -> Mutation:
        def run(data: dict[str, Any]) -> None:
            for track in tracks_of(data, kind):
                for prefix in prefixes:
                    node = track
                    for part in prefix.split(".")[1:]:
                        node = node[part.removesuffix("[]")]
                    drop_consts(node, prefix, consts)
        return run

    def each(find: Callable[[dict[str, Any]], list[dict[str, Any]]], prefix: str) -> Mutation:
        def run(data: dict[str, Any]) -> None:
            for node in find(data):
                drop_consts(node, prefix, consts)
        return run

    drum = "tracks[].program.drum.instruments[]"
    return {
        "T01": tracks(0, "tracks[]", "tracks[].program"),
        "M01": tracks(4, "tracks[]", "tracks[].program", "tracks[].program.midi"),
        "P04": each(lambda d: [i for t in tracks_of(d, 0) for i in t["program"]["drum"]["instruments"]], drum),
        "Q01": each(clips, CLIP),
        "Q02": each(events, f"{CLIP}.eventList.events[]"),
        "Q03": each(lambda d: d["samples"], "samples[]"),
        "Q04": each(lambda d: [s["value"] for s in d["sequences"]], "sequences[].value"),
    }


def drop_in_drum(key: str) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        for track in tracks_of(data, 0):
            track.pop(key, None)
    return run


def drop_in_program(key: str) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        for track in tracks_of(data, 0):
            track["program"].pop(key, None)
    return run


def disarm(data: dict[str, Any]) -> None:
    for track in data["tracks"]:
        track["recordArm"] = False


def build_cases(consts: set[str]) -> list[Case]:
    mins = minimal(consts)
    drum = ("tracks",)
    return [
        Case("Z01", "no-service", EMPTY, "Открылся ли проект без служебных треков Out, Submix, Return; что показал Live 2; виден ли `Drum 001`", ("tracks",), drop_types(7, 8, 9)),
        Case("Z02", "no-out", EMPTY, "Открылся ли проект без треков Out; выход звука на пэдах", ("tracks",), drop_types(9)),
        Case("Z03", "no-submix-return", EMPTY, "Открылся ли проект без Submix и Return при наличии Out", ("tracks",), drop_types(7, 8)),
        Case("R01", "no-mixer", EMPTY, "Открылся ли проект без ключа `mixer`; работает ли микшер", ("mixer",), drop_keys("mixer")),
        Case("R02", "no-scene", EMPTY, "Открылся ли проект без `scene`", ("scene",), drop_keys("scene")),
        Case("R03", "no-songs", EMPTY, "Открылся ли проект без `songs`; открывается ли Song Mode", ("songs",), drop_keys("songs")),
        Case("R04", "no-assign", EMPTY, "Открылся ли проект без назначений Q-Link, XY, пэдов, `midiLearnSettings`, `parameterSnapshotterData`", ASSIGN, drop_keys(*ASSIGN)),
        Case("R05", "no-gui", EMPTY, "Открылся ли проект без состояния интерфейса (`gui*`, `tui*`, клип-матрицы)", GUI, drop_keys(*GUI)),
        Case("R06", "min-root", EMPTY, "Открылся ли проект, где оставлены только `version`, `key`, темп, `samples`, `tracks`, `sequences`, текущие номера, `engineMode`", ("",), keep_root),
        Case("T01", "min-track", EMPTY, "Открылся ли проект, где у драм-трека убраны постоянные поля; виден ли трек, играют ли пэды", drum, mins["T01"]),
        Case("T02", "no-colour", EMPTY, "Открылся ли проект, где у драм-трека нет `colour`; какой цвет показан", drum, drop_in_drum("colour")),
        Case("T03", "no-mixable", EMPTY, "Открылся ли проект, где у драм-программы нет `mixable`; есть ли звук и громкость", drum, drop_in_program("mixable")),
        Case("T04", "arm-off", EMPTY, "`recordArm` выключен у всех треков: открылся ли проект, срабатывают ли пэды вообще, какой трек выбран", drum, disarm),
        Case("P01", "trigger-flip", PADS, "`triggerMode` пэдов 0 ↔ 2: чем отличается игра (одиночный удар или пока нажат)", drum, flip_trigger),
        Case("P02", "mono-off", PADS, "Флаг `monophonic` выключен при `polyphony` 1 (в исходном проекте включён): обрываются ли повторные удары", drum, set_pads(monophonic=False, polyphony=1)),
        Case("P03", "poly4", PADS, "`monophonic` выключен и `polyphony` 4: накладываются ли повторные удары", drum, set_pads(monophonic=False, polyphony=4)),
        Case("P04", "min-pad", PADS, "Открылся ли проект, где у пэдов убраны постоянные поля; звучат ли пэды", drum, mins["P04"]),
        Case("P05", "warp-on", PADS, "`warpEnable` true на заполненных пэдах: меняется ли звук, что показывает пэд", drum, set_pads(warpEnable=True)),
        Case("P06", "mute-group", PADS, "`whichMuteGroup` 1 у двух первых пэдов: глушит ли один другой", drum, mute_group),
        Case("Q01", "min-clip", PADS, "Открылся ли проект, где у клипов убраны постоянные поля; звучат ли ноты", ("sequences",), mins["Q01"]),
        Case("Q02", "min-event", PADS, "Открылся ли проект, где у нот убраны постоянные поля; звучат ли ноты", ("sequences",), mins["Q02"]),
        Case("Q03", "min-sample", PADS, "Открылся ли проект, где у записей сэмплов убраны постоянные поля; находит ли Live 2 файлы", ("samples",), mins["Q03"]),
        Case("Q04", "min-sequence", PADS, "Открылся ли проект, где у секвенции убраны постоянные поля; длина и темп на месте", ("sequences",), mins["Q04"]),
        Case("M01", "min-midi", MIDI, "Открылся ли проект, где у MIDI-трека убраны постоянные поля; ноты на месте, выход не задан", drum, mins["M01"]),
    ]


def write_case(case: Case, base: Path, out: Path) -> Path:
    project = patch.load(base)
    case.mutate(project.data)
    name = f"{case.id} {case.slug}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.xpj"
    path.write_bytes(patch.pack(patch.render(project)))
    source = base.parent / f"{base.stem}_[ProjectData]"
    target = out / f"{name}_[ProjectData]"
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("._*", ".DS_Store"))
    else:
        target.mkdir(exist_ok=True)
    return path


def remove_stale(out: Path, items: list[Case]) -> list[str]:
    """Удаляет проекты прежних запусков, которых нет в списке: на Live 2 уходит вся папка."""
    names = {f"{c.id} {c.slug}" for c in items}
    gone = []
    for entry in sorted(out.glob("[A-Z][0-9][0-9] *")) if out.is_dir() else []:
        if entry.name.removesuffix(".xpj").removesuffix("_[ProjectData]") not in names:
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
            gone.append(entry.name)
    return gone


def checklist(items: list[Case]) -> str:
    lines = [
        "# Чек-лист спайка 9, раунд 1",
        "",
        f"Один заход на Live 2, до 30 минут. Скопируй на SD всю папку `test-projects/mpc/spike9/`, имена не меняй. Открой каждый проект, запусти пэды и секвенцию, заполни таблицу. Если проект не открылся, запиши текст ошибки и иди дальше. Кейсы собраны `cases.py`, на каждый одно изменение исходного проекта. Всего {len(items)}.",
        "",
        "| Проект | Что проверить | Результат |",
        "|---|---|---|",
    ]
    lines += [f"| `{c.id} {c.slug}` | {c.text} | |" for c in items]
    lines += ["", "## Готово", "", "Пришли таблицу.", ""]
    return "\n".join(lines)


def load_consts() -> set[str]:
    rows = registry.parse_schema((registry.MPC / "schema.tsv").read_text(encoding="utf-8"))
    return {r.path.removeprefix("data.") for r in rows if registry.classify(r) == "const"}


def main() -> int:
    items = build_cases(load_consts())
    assert len(items) <= MAX_CASES
    (HERE / "CHECKLIST.md").write_text(checklist(items), encoding="utf-8")
    if "--checklist" in sys.argv[1:]:
        return 0
    for name in remove_stale(OUT, items):
        print(f"удалено: {name}")
    for case in items:
        print(write_case(case, PROJECTS / case.base, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
