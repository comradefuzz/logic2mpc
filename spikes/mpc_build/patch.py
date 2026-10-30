#!/usr/bin/env python3
"""Собирает проверочные проекты .xpj из шаблона для спайка 8. Не код продукта.

    patch.py check <project.xpj>     проверить побайтовый повтор JSON
    patch.py build                   собрать все кейсы в test-projects/mpc/spike8/

Числа хранятся как текст: Live 2 пишет float с 17 знаками, и обычный json их округлит.
"""
from __future__ import annotations

import copy
import gzip
import json
import shutil
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MPC = ROOT / "test-projects" / "mpc"
OUT = MPC / "spike8"
HEADER_LINES = 5
PPQ = 960
BAR = PPQ * 4


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


def clip(project: Project, sequence: int, track: str) -> dict[str, Any]:
    clips = project.data["sequences"][sequence]["value"]["trackClipMaps"][0]
    return next(c["value"] for c in clips if c["key"] == track)


def note_template(project: Project) -> dict[str, Any]:
    for sequence in project.data["sequences"]:
        for clips in sequence["value"]["trackClipMaps"]:
            for item in clips:
                for event in item["value"]["eventList"]["events"]:
                    if "note" in event:
                        return event
    raise ValueError("в шаблоне нет ни одной ноты")


def make_event(template: dict[str, Any], tick: int, pitch: int, velocity: float, length: int) -> dict[str, Any]:
    event = copy.deepcopy(template)
    event["time"] = tick
    event["note"]["note"] = pitch
    event["note"]["velocity"] = float(velocity)
    event["note"]["length"] = length
    return event


def set_notes(
    project: Project,
    sequence: int,
    track: str,
    notes: list[tuple[int, int, float, int]],
    template: dict[str, Any] | None = None,
) -> None:
    template = template or note_template(project)
    clip(project, sequence, track)["eventList"]["events"] = [
        make_event(template, *note) for note in notes
    ]


def insert_track(project: Project, track: dict[str, Any], name: str) -> None:
    """Ставит трек перед служебными, добавляет пустой клип в каждую секвенцию."""
    track["name"] = name
    track["program"]["name"] = name
    tracks = project.data["tracks"]
    position = next(i for i, t in enumerate(tracks) if t["program"]["type"] >= 7)
    tracks.insert(position, track)
    for sequence in project.data["sequences"]:
        clips = sequence["value"]["trackClipMaps"][0]
        base = copy.deepcopy(clips[0])
        base["key"] = name
        base["value"]["name"] = name
        base["value"]["eventList"]["events"] = []
        clips.append(base)
        clips.sort(key=lambda c: c["key"])


def frames(path: Path) -> int:
    with wave.open(str(path)) as audio:
        return audio.getnframes()


def set_pad(program: dict[str, Any], pad: int, entry: dict[str, Any], length: int) -> None:
    instruments = program["drum"]["instruments"]
    instruments[pad] = copy.deepcopy(instruments[0])
    layer = instruments[pad]["layersv"][0]
    layer["sampleName"] = entry["name"]
    layer["sampleFile"] = entry["path"]
    layer["sliceInfo"]["End"] = length - 1
    program["samples"].append(copy.deepcopy(entry))


def clear_pads(program: dict[str, Any]) -> None:
    instruments = program["drum"]["instruments"]
    for pad in range(len(instruments) - 1):
        instruments[pad] = copy.deepcopy(instruments[-1])
    program["samples"] = []


def eighths(pitch: int) -> list[tuple[int, int, float, int]]:
    return [(i * PPQ // 2, pitch, 1.0 if i % 2 == 0 else 0.5, PPQ // 4) for i in range(8)]


def write(project: Project, name: str, samples: list[Path]) -> Path:
    target = OUT / f"{name}.xpj"
    folder = OUT / f"{name}_[ProjectData]"
    folder.mkdir(parents=True, exist_ok=True)
    for sample in samples:
        shutil.copy2(sample, folder / sample.name)
    target.write_bytes(pack(render(project)))
    return target


def source_track(rich: Project, name: str) -> dict[str, Any]:
    return copy.deepcopy(next(t for t in rich.data["tracks"] if t["name"] == name))


def rich_entry(rich: Project, path: str) -> dict[str, Any]:
    return next(s for s in rich.data["samples"] if s["path"] == path)


def add_rich_samples(project: Project, rich: Project, track: dict[str, Any]) -> list[Path]:
    folder = MPC / "Rataklang - Brassic_[ProjectData]"
    paths = []
    for entry in track["program"]["samples"]:
        project.data["samples"].append(copy.deepcopy(rich_entry(rich, entry["path"])))
        paths.append(folder / entry["path"])
    return paths


def add_second_sequence(project: Project) -> None:
    sequences = project.data["sequences"]
    second = copy.deepcopy(sequences[-1])
    second["key"] = 1
    second["value"]["name"] = "Sequence 02"
    second["value"]["bpm"] = float(project.data["masterTempo"])
    sequences.insert(0, second)


def build() -> None:
    template = MPC / "Spike4 A.xpj"
    base_folder = MPC / "Spike4 A_[ProjectData]"
    rich = load(MPC / "Rataklang - Brassic.xpj")
    amen = base_folder / "cw_amen01_175.wav"
    kick = MPC / "Rataklang - Brassic_[ProjectData]" / "BILLY KICK V10 - A.wav"
    kick_entry = rich_entry(rich, kick.name)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("T?? *"):
        if "resaved" in old.name:
            continue
        shutil.rmtree(old) if old.is_dir() else old.unlink()

    item = load(template)
    write(item, "T01 same", [amen])

    item = load(template)
    set_notes(item, 0, "Drum 001", [(PPQ * 2, 36, 1.0, 1199)])
    write(item, "T02 note", [amen])

    item = load(template)
    set_notes(item, 0, "Drum 001", eighths(36))
    write(item, "T03 notes", [amen])

    item = load(template)
    set_pad(item.data["tracks"][0]["program"], 1, kick_entry, frames(kick))
    item.data["samples"].append(copy.deepcopy(kick_entry))
    set_notes(item, 0, "Drum 001", [(i * PPQ, 36 + i % 2, 1.0, PPQ // 2) for i in range(8)])
    write(item, "T04 pad", [amen, kick])

    item = load(template)
    event = note_template(item)
    insert_track(item, copy.deepcopy(item.data["tracks"][0]), "Drum 002")
    set_notes(item, 0, "Drum 002", [(i * PPQ + PPQ // 2, 36, 0.7, PPQ // 4) for i in range(8)], event)
    write(item, "T05 track", [amen])

    for number, name, pitch in ((6, "LD True Survivor", 60), (7, "BS Tube", 48), (8, "MIDI Minilogue", 48)):
        item = load(template)
        event = note_template(item)
        track = source_track(rich, name)
        samples = add_rich_samples(item, rich, track)
        insert_track(item, track, name)
        set_notes(item, 0, name, eighths(pitch), event)
        label = {6: "keygroup", 7: "plugin", 8: "midi"}[number]
        write(item, f"T{number:02d} {label}", [amen, *samples])

    item = load(template)
    item.data["masterTempo"] = 97.0
    item.data["sequences"][0]["value"]["bpm"] = 97.0
    add_second_sequence(item)
    set_notes(item, 0, "Drum 001", eighths(36))
    write(item, "T09 tempo", [amen])

    item = load(template)
    event = note_template(item)
    item.data["masterTempo"] = 97.0
    item.data["sequences"][0]["value"]["bpm"] = 97.0
    set_pad(item.data["tracks"][0]["program"], 1, kick_entry, frames(kick))
    item.data["samples"].append(copy.deepcopy(kick_entry))
    item.data["tracks"][0]["name"] = "Drums"
    item.data["tracks"][0]["program"]["name"] = "Drums"
    clips = item.data["sequences"][0]["value"]["trackClipMaps"][0]
    clips[0]["key"] = "Drums"
    clips[0]["value"]["name"] = "Drums"
    clips.sort(key=lambda c: c["key"])
    hands = copy.deepcopy(item.data["tracks"][0])
    clear_pads(hands["program"])
    item.data["tracks"].insert(0, hands)
    hands["name"] = "HANDS"
    hands["program"]["name"] = "HANDS"
    base = copy.deepcopy(clips[0])
    base["key"] = "HANDS"
    base["value"]["name"] = "HANDS"
    base["value"]["eventList"]["events"] = []
    clips.append(base)
    clips.sort(key=lambda c: c["key"])
    samples = [amen, kick]
    for name, pitch in (("LD True Survivor", 60), ("BS Tube", 48), ("MIDI Minilogue", 48)):
        track = source_track(rich, name)
        samples += add_rich_samples(item, rich, track)
        insert_track(item, track, name)
        set_notes(item, 0, name, eighths(pitch), event)
    set_notes(item, 0, "Drums", [(i * PPQ, 36 + i % 2, 1.0, PPQ // 2) for i in range(16)], event)
    write(item, "T10 full", samples)

    for path in sorted(p for p in OUT.glob("*.xpj") if "resaved" not in p.name):
        size = len(gzip.decompress(path.read_bytes()))
        names = [t["name"] for t in load(path).data["tracks"] if t["program"]["type"] < 7]
        print(f"{path.name}: {path.stat().st_size} байт, JSON {size}, треки {names}")


def check(path: Path) -> None:
    raw = gzip.decompress(path.read_bytes())
    same = render(parse(raw)) == raw
    print(f"{path.name}: {'совпало побайтно' if same else 'РАСХОЖДЕНИЕ'}, {len(raw)} байт")
    if not same:
        sys.exit(1)


def main() -> None:
    if sys.argv[1] == "check":
        check(Path(sys.argv[2]))
    elif sys.argv[1] == "build":
        build()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
