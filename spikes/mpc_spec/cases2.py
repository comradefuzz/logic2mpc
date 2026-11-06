#!/usr/bin/env python3
"""Кейсы спайка 9, раунд 2: какие постоянные поля пэда, слоя и события обязательны.

    cases2.py             пишет проекты в test-projects/mpc/spike9b и CHECKLIST2.md
    cases2.py --checklist только CHECKLIST2.md

Раунд 1 (P04, Q02) показал: без постоянных полей пэд молчит, а ноты не видны в гриде. Здесь поля убираются группами
из проекта `spike7/D01 pads16`, по одной группе на кейс.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
from cases import Case, Mutation  # noqa: E402

OUT = cases.PROJECTS / "mpc" / "spike9b"
MAX_CASES = 25

PAD_TUNE = ("coarseTune", "fineTune", "velocityScale")
PAD_ROUTE = ("layerCrossfade", "layerCrossfadeX", "layerCrossfadeY", "midiOutBehaviour", "midiOutChannel", "midiOutNote")
PAD_FLAGS = ("editAllLayers", "ignoreBaseNote", "bpmLock", "loopLock", "articulationUseXY", "emulationProfile", "partialPresetName")
LAYER_REST = (
    "OffsetRandom", "OscillatorType", "PanRandom", "active", "direction", "fineTune", "layerLoopModeOverridesSliceLoopMode",
    "loop", "loopCrossfadeLength", "loopEnd", "loopFineTune", "loopMode", "loopStart", "mute", "offset", "oscillatorMode",
    "oscillatorSubTypeName", "pan", "pitchRandom", "playbackOffset", "sampleEnd", "sampleStart", "sliceCycleLength",
    "sliceIncrement",
)
NOTE_REST = ("probability", "ratchet", "articulation")
MODIFIERS = tuple(f"{p}{i}" for i in range(16) for p in ("modifierValue", "modifierActiveState"))


def pads(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for t in cases.tracks_of(data, 0) for i in t["program"]["drum"]["instruments"]]


def layers(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [layer for pad in pads(data) for layer in pad["layersv"]]


def notes(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e["note"] for e in cases.events(data) if "note" in e]


def drop(find: Callable[[dict[str, Any]], list[dict[str, Any]]], keys: tuple[str, ...]) -> Mutation:
    def run(data: dict[str, Any]) -> None:
        for node in find(data):
            for key in keys:
                node.pop(key, None)
    return run


def keep_only(find: Callable[[dict[str, Any]], list[dict[str, Any]]], kept: tuple[str, ...], pool: tuple[str, ...]) -> Mutation:
    return drop(find, tuple(k for k in pool if k not in kept))


def build_cases() -> list[Case]:
    pad_all = PAD_TUNE + PAD_ROUTE + PAD_FLAGS
    base = "mpc/spike7/D01 pads16.xpj"
    t = ("sequences",)
    return [
        Case("B01", "pad-version", base, "Пэды без поля `version`, остальное на месте: назначения пэдов, звук, уровни", ("tracks",), drop(pads, ("version",))),
        Case("B02", "pad-no-tune", base, "Пэды без `coarseTune`, `fineTune`, `velocityScale`: звук, уровни", ("tracks",), drop(pads, PAD_TUNE)),
        Case("B03", "pad-no-route", base, "Пэды без `layerCrossfade*` и `midiOut*`: звук, уровни", ("tracks",), drop(pads, PAD_ROUTE)),
        Case("B04", "pad-no-flags", base, "Пэды без `editAllLayers`, `ignoreBaseNote`, `bpmLock`, `loopLock`, `articulationUseXY`, `emulationProfile`, `partialPresetName`: звук, уровни", ("tracks",), drop(pads, PAD_FLAGS)),
        Case("B05", "pad-only-version", base, "Все постоянные поля пэда убраны, кроме `version`: назначения, звук, уровни", ("tracks",), drop(pads, pad_all)),
        Case("B06", "layer-version", base, "Слои без поля `version`: назначения, звук", ("tracks",), drop(layers, ("version",))),
        Case("B07", "layer-rest", base, "Слои без остальных постоянных полей, `version` на месте: назначения, звук", ("tracks",), drop(layers, LAYER_REST)),
        Case("E01", "event-version", base, "События без `version`: видны ли ноты в гриде, играют ли", t, drop(cases.events, ("version",))),
        Case("E02", "event-selected", base, "События без `selected`: видны ли ноты в гриде, играют ли", t, drop(cases.events, ("selected",))),
        Case("E03", "note-version", base, "Ноты без `version`: видны ли ноты в гриде, играют ли", t, drop(notes, ("version",))),
        Case("E04", "note-modifiers", base, "Ноты без `modifierValue*` и `modifierActiveState*`: видны ли ноты, играют ли", t, drop(notes, MODIFIERS)),
        Case("E05", "note-rest", base, "Ноты без `probability`, `ratchet`, `articulation`: видны ли ноты, играют ли", t, drop(notes, NOTE_REST)),
    ]


def checklist(items: list[Case]) -> str:
    lines = [
        "# Чек-лист спайка 9, раунд 2",
        "",
        f"Один заход на Live 2. Скопируй на SD всю папку `test-projects/mpc/spike9b/`, имена не меняй. Открой каждый проект, запусти пэды и секвенцию, запиши результат. Это раунд 2: он ищет, какие постоянные поля пэда, слоя и события обязательны (в раунде 1 без всех постоянных полей `P04` молчал, а у `Q02` не было нот в гриде). Каждый кейс убирает одну группу полей. Всего {len(items)}.",
        "",
        "| Проект | Что проверить | Результат |",
        "|---|---|---|",
    ]
    lines += [f"| `{c.id} {c.slug}` | {c.text} | |" for c in items]
    lines += ["", "## Готово", "", "Пришли таблицу.", ""]
    return "\n".join(lines)


def main() -> int:
    items = build_cases()
    assert len(items) <= MAX_CASES
    (HERE / "CHECKLIST2.md").write_text(checklist(items), encoding="utf-8")
    if "--checklist" in sys.argv[1:]:
        return 0
    for name in cases.remove_stale(OUT, items):
        print(f"удалено: {name}")
    for case in items:
        print(cases.write_case(case, cases.PROJECTS / case.base, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
