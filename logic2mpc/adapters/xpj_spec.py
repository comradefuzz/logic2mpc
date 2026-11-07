"""Описание формата `.xpj` для экспорта: объекты, которые создаёт сборка.

Файлы `logic2mpc/spec/*.json` порождает `scripts/build_spec.py` из `docs/formats/mpc/export.tsv` и эталонов: в них нет
полей, помеченных в реестре как необязательные (`required = no`), значения остальных как в Live 2 (`Empty.xpj`) и
`D01 pads16`. Переменные поля задаются здесь. Донорского проекта сборка не читает.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .mpcfile import Number

SPEC = Path(__file__).resolve().parent.parent / "spec"
SEED_MASK = 2**31 - 1


@lru_cache(maxsize=None)
def _text(name: str) -> str:
    return (SPEC / name).read_text(encoding="utf-8")


def _object(name: str) -> dict[str, Any]:
    return json.loads(_text(name), parse_float=Number)


def header() -> bytes:
    return (SPEC / "header.txt").read_bytes()


def number(value: float) -> Number:
    return Number(str(float(value)))


# Цвета новых драм-треков Live 2: круг из 21 значения (MPC-R-014), первый трек 0x55FF00.
TRACK_PALETTE = (
    0x55FF00, 0x00FF80, 0x00AAFF, 0x5200FF, 0xFF00FF, 0xFF4400, 0xE6FF00, 0x11FF00, 0x00FFC4, 0x0066FF, 0x6F00FF,
    0xFF00BB, 0xFF8800, 0xA2FF00, 0x00FF33, 0x00F7FF, 0x0022FF, 0xB200FF, 0xFF0077, 0xFF0000, 0xFFD500,
)


def track_colour(number: int) -> int:
    """Цвет трека или дорожки Logic под номером `number` (с 0): круг Live 2."""
    return TRACK_PALETTE[number % len(TRACK_PALETTE)]


def paint_pads(track: dict[str, Any], colours: dict[int, int]) -> None:
    """Красит пэды драм-трека по одному: `programPads.pads.valueN` и режим SINGLE PAD (`Universal` false), MPC-R-015."""
    pads = track["program"]["programPads"]
    for index, colour in colours.items():
        pads["pads"][f"value{index}"] = colour
    pads["Universal"]["value0"] = False


def seed(index: int, layer: int = 0) -> int:
    """Детерминированное зерно воспроизведения: Live 2 пишет случайные, сборка должна повторяться."""
    return (index * 2654435761 + layer * 40503 + 12345) & SEED_MASK


def root(bpm: float) -> dict[str, Any]:
    data = _object("root.json")
    data["masterTempo"] = float(bpm)
    return data


def drum_track(name: str, armed: bool, colour: int | None = None) -> dict[str, Any]:
    """Пустой драм-трек. Пэды добавляются отдельно, `recordArm` задаётся явно, MPC-111, цвет задаётся явно."""
    track = _object("track.json")
    track["name"] = track["program"]["name"] = name
    track["recordArm"] = armed
    if colour is not None:
        track["colour"] = colour
    return track


def pad(
    index: int, sample: tuple[str, str, int] | None, bpm: float, trigger_mode: int = 0, mute_group: int = 0,
) -> dict[str, Any]:
    """Пэд драм-программы. `sample` это имя, файл и число кадров. `index` уникален в проекте и даёт зёрна.

    `trigger_mode`: 0 One Shot, 2 Note On (MPC-115). `mute_group`: 0 нет группы, 1 и больше общая группа пэдов.
    """
    made = _object("pad.json")
    made["triggerMode"] = trigger_mode
    made["whichMuteGroup"] = mute_group
    made["randomPlaySeed"] = seed(index)
    for number_, layer in enumerate(made["layersv"]):
        layer["sliceIncrementRngSeed"] = seed(index, number_ + 1)
    if sample:
        name, file, frames = sample
        layer = made["layersv"][0]
        layer["sampleName"], layer["sampleFile"] = name, file
        layer["sliceInfo"]["End"] = frames - 1
        made["tempo"] = number(bpm)
    return made


def sample_entry(name: str, path: str, bpm: float, in_program: bool = False) -> dict[str, Any]:
    """Запись сэмпла: в пуле проекта (`samples[]`) или в программе трека (`program.samples[]`), состав полей разный."""
    entry = _object("program_sample.json" if in_program else "sample.json")
    entry["name"], entry["path"] = name, path
    entry["metadata"]["tempo"] = number(bpm)
    return entry


def sequence(key: int, name: str, bars: int, pulses: int, bpm: float) -> dict[str, Any]:
    value = _object("sequence.json")
    value["name"], value["bpm"] = name, float(bpm)
    value["lengthBars"] = value["loopEndBar"] = bars
    value["lengthPulses"] = value["loopEndPulses"] = pulses
    return {"key": key, "value": value}


def clip(name: str, pulses: int) -> dict[str, Any]:
    value = _object("clip.json")
    value["name"] = name
    value["endPulses"] = value["loopEndPulses"] = pulses
    return {"key": name, "value": value}


def note_event(tick: int, pitch: int, velocity: float, length: int) -> dict[str, Any]:
    event = _object("event.json")
    event["time"] = tick
    event["note"]["note"] = pitch
    event["note"]["velocity"] = float(velocity)
    event["note"]["length"] = length
    return event
