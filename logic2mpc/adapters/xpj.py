"""Сборка проекта MPC из шаблона. Устройство файла описано в docs/formats/mpc/, приём из spikes/mpc_build/patch.py.

Числа хранятся как текст: Live 2 пишет float с 17 знаками, и обычный json их округлит.
"""
from __future__ import annotations

import copy
import gzip
import json
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.model import BAR
from ..core.names import transliterate
from ..core.plan import Group, Plan, PlanPiece
from ..core.sections import Section, place

HEADER_LINES = 5
PADS = 128
TEMPLATE = Path(__file__).resolve().parent.parent / "template" / "template.xpj"
BASE_TRACK = "Drum 001"
HANDS = "HANDS"
MIN_VELOCITY = 0.05


class Number(str):
    """Число JSON в исходной записи."""


@dataclass
class Project:
    header: bytes
    data: dict[str, Any]


def parse(raw: bytes) -> Project:
    parts = raw.split(b"\n", HEADER_LINES)
    header = b"\n".join(parts[:HEADER_LINES]) + b"\n"
    root = json.loads(parts[HEADER_LINES], parse_float=Number)
    return Project(header, root["data"])


def load(path: Path) -> Project:
    return parse(gzip.decompress(path.read_bytes()))


def dump(node: Any) -> str:
    if isinstance(node, Number):
        return str(node)
    if isinstance(node, dict):
        if not node:
            return "{}"
        items = ",\n".join(f"{json.dumps(k, ensure_ascii=False)}: {dump(v)}" for k, v in node.items())
        return "{\n" + items + "\n}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return "[\n" + ",\n".join(dump(v) for v in node) + "\n]"
    return json.dumps(node, ensure_ascii=False)


def render(project: Project) -> bytes:
    return project.header + dump({"data": project.data}).encode("utf-8")


def pack(raw: bytes) -> bytes:
    data = bytearray(gzip.compress(raw, mtime=0))
    data[8] = 0  # заголовок как у файлов с Live 2
    data[9] = 3
    return bytes(data)


def frames(path: Path) -> int:
    """Число кадров по заголовку RIFF."""
    raw = path.read_bytes()
    offset = 12
    block = 0
    while offset + 8 <= len(raw):
        size = struct.unpack_from("<I", raw, offset + 4)[0]
        if raw[offset : offset + 4] == b"fmt ":
            block = struct.unpack_from("<H", raw, offset + 20)[0]
        elif raw[offset : offset + 4] == b"data":
            return size // block
        offset += 8 + size + size % 2
    raise ValueError(f"нет данных в {path}")


def note_template(project: Project) -> dict[str, Any]:
    for sequence in project.data["sequences"]:
        for clips in sequence["value"]["trackClipMaps"]:
            for item in clips:
                for event in item["value"]["eventList"]["events"]:
                    if "note" in event:
                        return copy.deepcopy(event)
    raise ValueError("в шаблоне нет ни одной ноты")


def make_event(template: dict[str, Any], tick: int, pitch: int, velocity: float, length: int) -> dict[str, Any]:
    event = copy.deepcopy(template)
    event["time"] = tick
    event["note"]["note"] = pitch
    event["note"]["velocity"] = float(velocity)
    event["note"]["length"] = length
    return event


def clear_pads(program: dict[str, Any]) -> None:
    instruments = program["drum"]["instruments"]
    for pad in range(len(instruments) - 1):
        instruments[pad] = copy.deepcopy(instruments[-1])
    program["samples"] = []


def set_pad(program: dict[str, Any], filled: dict[str, Any], pad: int, entry: dict[str, Any], length: int) -> None:
    program["drum"]["instruments"][pad] = copy.deepcopy(filled)
    layer = program["drum"]["instruments"][pad]["layersv"][0]
    layer["sampleName"] = entry["name"]
    layer["sampleFile"] = entry["path"]
    layer["sliceInfo"]["End"] = length - 1
    program["samples"].append(copy.deepcopy(entry))


def insert_track(project: Project, track: dict[str, Any], name: str) -> None:
    """Ставит трек перед служебными, добавляет пустой клип в секвенцию шаблона."""
    track["name"] = name
    track["program"]["name"] = name
    tracks = project.data["tracks"]
    position = next(i for i, t in enumerate(tracks) if t["program"]["type"] >= 7)
    tracks.insert(position, track)
    clips = project.data["sequences"][0]["value"]["trackClipMaps"][0]
    base = copy.deepcopy(clips[0])
    base["key"] = name
    base["value"]["name"] = name
    base["value"]["eventList"]["events"] = []
    clips.append(base)
    clips.sort(key=lambda c: c["key"])


def rename_first_track(project: Project, name: str) -> dict[str, Any]:
    """Трек шаблона становится пустым HANDS: так он остаётся первым."""
    track = project.data["tracks"][0]
    track["name"] = name
    track["program"]["name"] = name
    clear_pads(track["program"])
    clips = project.data["sequences"][0]["value"]["trackClipMaps"][0]
    clip = next(c for c in clips if c["key"] == BASE_TRACK)
    clip["key"] = name
    clip["value"]["name"] = name
    clip["value"]["eventList"]["events"] = []
    clips.sort(key=lambda c: c["key"])
    return track


def set_length(value: dict[str, Any], section: Section) -> None:
    pulses = section.bars * BAR
    value["lengthBars"] = value["loopEndBar"] = section.bars
    value["lengthPulses"] = value["loopEndPulses"] = pulses
    for clips in value["trackClipMaps"]:
        for item in clips:
            item["value"]["endPulses"] = item["value"]["loopEndPulses"] = pulses


def make_sequences(project: Project, sections: list[Section]) -> None:
    base = project.data["sequences"][0]
    made = []
    for number, section in enumerate(sections):
        item = copy.deepcopy(base)
        item["key"] = number
        item["value"]["name"] = transliterate(section.name)
        set_length(item["value"], section)
        made.append(item)
    project.data["sequences"] = list(reversed(made))
    project.data["currentSequence"] = 0


def exported(group: Group) -> list[PlanPiece]:
    return [p for t in group.tracks for p in t.pieces if p.export]


def clip_of(value: dict[str, Any], track: str) -> dict[str, Any]:
    return next(c["value"] for c in value["trackClipMaps"][0] if c["key"] == track)


def notes_of(value: dict[str, Any], track: str) -> list[tuple[int, int]]:
    return [(e["time"], e["note"]["note"]) for e in clip_of(value, track)["eventList"]["events"]]


def add_notes(
    project: Project, track: str, pitch: int, piece: PlanPiece, sections: list[Section], template: dict[str, Any]
) -> None:
    by_key = {s["key"]: s["value"] for s in project.data["sequences"]}
    loudest = max((o.gain for o in piece.occurrences), default=0.0)
    for occurrence in piece.occurrences:
        number, attack = place(occurrence.tick, sections)
        tick = max(attack - piece.lead, 0)
        room = sections[number].bars * BAR - tick
        velocity = max(occurrence.gain / loudest, MIN_VELOCITY) if loudest else 1.0
        event = make_event(template, tick, pitch, velocity, max(min(occurrence.length or piece.ticks, room), 1))
        clip_of(by_key[number], track)["eventList"]["events"].append(event)


def check(plan: Plan, samples: Path) -> None:
    """Всё проверяется до записи: без сэмпла Live 2 покажет Sample not found, см. MPC-083."""
    for group in plan.groups:
        pieces = exported(group)
        if len(pieces) > PADS:
            raise ValueError(f"группа {group.name}: {len(pieces)} кусков при лимите {PADS} пэдов")
    missing = sorted(p.file for g in plan.groups for p in exported(g) if not (samples / p.file).is_file())
    if missing:
        raise FileNotFoundError("нет сэмплов: " + ", ".join(missing))


def write_project(plan: Plan, samples: Path, out: Path, name: str) -> Path:
    check(plan, samples)
    name = transliterate(name)
    project = load(TEMPLATE)
    template = note_template(project)
    data = project.data
    filled = copy.deepcopy(data["tracks"][0]["program"]["drum"]["instruments"][0])
    entry_base = copy.deepcopy(data["samples"][0])
    entry_base["metadata"]["tempo"] = Number(str(float(plan.bpm)))
    data["masterTempo"] = float(plan.bpm)
    data["sequences"][0]["value"]["bpm"] = float(plan.bpm)
    data["samples"] = []
    hands = rename_first_track(project, HANDS)
    copies: list[tuple[Path, str]] = []
    chosen: list[tuple[str, list[PlanPiece]]] = []
    for group in plan.groups:
        pieces = exported(group)
        track = copy.deepcopy(hands)
        for pad, piece in enumerate(pieces):
            entry = copy.deepcopy(entry_base)
            entry["name"] = piece.name
            entry["path"] = f"{piece.name}.wav"
            data["samples"].append(copy.deepcopy(entry))
            set_pad(track["program"], filled, pad, entry, frames(samples / piece.file))
            copies.append((samples / piece.file, entry["path"]))
        title = transliterate(group.name)
        insert_track(project, track, title)
        chosen.append((title, pieces))
    make_sequences(project, plan.sections)
    for title, pieces in chosen:
        map_notes = next(t for t in data["tracks"] if t["name"] == title)["program"]["padNoteMap"]["noteForPad"]
        for pad, piece in enumerate(pieces):
            add_notes(project, title, map_notes[f"value{pad}"], piece, plan.sections, template)
    for sequence in data["sequences"]:
        for clips in sequence["value"]["trackClipMaps"]:
            for item in clips:
                item["value"]["eventList"]["events"].sort(key=lambda e: e["time"])
    out.mkdir(parents=True, exist_ok=True)
    folder = out / f"{name}_[ProjectData]"
    folder.mkdir(exist_ok=True)
    for source, target in copies:
        shutil.copy2(source, folder / target)
    path = out / f"{name}.xpj"
    path.write_bytes(pack(render(project)))
    return path
