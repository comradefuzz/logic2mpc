#!/usr/bin/env python3
"""Собирает проверочные проекты .xpj из шаблона для спайка 8. Не код продукта.

    patch.py check <project.xpj>     проверить побайтовый повтор JSON
    patch.py build                   собрать кейсы спайка 8 в test-projects/mpc/spike8/
    patch.py build7                  собрать кейсы спайка 7 в test-projects/mpc/spike7/

Числа хранятся как текст: Live 2 пишет float с 17 знаками, и обычный json их округлит.
"""
from __future__ import annotations

import copy
import gzip
import json
import shutil
import struct
import subprocess
import sys
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
    """Число кадров по заголовку RIFF: wave не читает float."""
    raw = path.read_bytes()
    offset = 12
    block = 0
    while offset + 8 <= len(raw):
        size = struct.unpack_from("<I", raw, offset + 4)[0]
        if raw[offset:offset + 4] == b"fmt ":
            block = struct.unpack_from("<H", raw, offset + 20)[0]
        elif raw[offset:offset + 4] == b"data":
            return size // block
        offset += 8 + size + size % 2
    raise ValueError(f"нет данных в {path}")


def set_pad(program: dict[str, Any], pad: int, entry: dict[str, Any], length: int) -> None:
    instruments = program["drum"]["instruments"]
    instruments[pad] = copy.deepcopy(instruments[0])
    layer = instruments[pad]["layersv"][0]
    layer["sampleName"] = entry["name"]
    layer["sampleFile"] = entry["path"]
    layer["sliceInfo"]["End"] = length - 1
    program["samples"].append(copy.deepcopy(entry))


def set_keygroup(
    program: dict[str, Any], entry: dict[str, Any], length: int, root: int, key_track: bool
) -> None:
    """Одна зона на всю клавиатуру из одного сэмпла."""
    instruments = program["drum"]["instruments"]
    blank = copy.deepcopy(instruments[-1])
    for number in range(len(instruments) - 1):
        instruments[number] = copy.deepcopy(blank)
    zone = instruments[0]
    zone["lowNote"], zone["highNote"] = 0, 127
    layer = zone["layersv"][0]
    layer["sampleName"] = entry["name"]
    layer["sampleFile"] = entry["path"]
    layer["sliceInfo"]["End"] = length - 1
    layer["rootNote"] = root
    layer["keyTrackEnable"] = key_track
    program["keygroup"]["numKeygroups"] = 1
    program["samples"] = [copy.deepcopy(entry)]


def set_velocity_layers(
    program: dict[str, Any], pad: int, sounds: list[tuple[dict[str, Any], int]]
) -> None:
    """Делит диапазон скорости поровну между слоями пэда."""
    instruments = program["drum"]["instruments"]
    layers = instruments[pad]["layersv"]
    step = 128 // len(sounds)
    for number, (entry, length) in enumerate(sounds):
        layer = layers[number]
        layer["sampleName"] = entry["name"]
        layer["sampleFile"] = entry["path"]
        layer["sliceInfo"]["End"] = length - 1
        layer["velocityStart"] = number * step
        layer["velocityEnd"] = 127 if number == len(sounds) - 1 else (number + 1) * step - 1
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


OUT7 = MPC / "spike7"
RICH = MPC / "Rataklang - Brassic_[ProjectData]"


def write7(project: Project, name: str, samples: list[Path]) -> None:
    folder = OUT7 / f"{name}_[ProjectData]"
    folder.mkdir(parents=True, exist_ok=True)
    for sample in samples:
        shutil.copy2(sample, folder / sample.name)
    (OUT7 / f"{name}.xpj").write_bytes(pack(render(project)))


def new_entry(rich: Project, path: Path, name: str | None = None) -> dict[str, Any]:
    entry = copy.deepcopy(rich.data["samples"][0])
    entry["name"] = name or path.stem
    entry["path"] = (name or path.stem) + path.suffix
    return entry


def fill_pads(project: Project, rich: Project, count: int) -> list[Path]:
    """Заполняет пэды сэмплами примера по кругу, в проект идёт каждый файл один раз."""
    program = project.data["tracks"][0]["program"]
    files = sorted(p for p in RICH.iterdir() if p.suffix == ".wav" and "Audio" not in p.name)
    used: dict[str, Path] = {}
    template = copy.deepcopy(program["drum"]["instruments"][0])
    program["samples"] = []
    project.data["samples"] = []
    for pad in range(count):
        path = files[pad % len(files)]
        entry = rich_entry(rich, path.name)
        program["drum"]["instruments"][pad] = copy.deepcopy(template)
        layer = program["drum"]["instruments"][pad]["layersv"][0]
        layer["sampleName"], layer["sampleFile"] = entry["name"], entry["path"]
        layer["sliceInfo"]["End"] = frames(path) - 1
        if path.name not in used:
            used[path.name] = path
            program["samples"].append(copy.deepcopy(entry))
            project.data["samples"].append(copy.deepcopy(entry))
    return list(used.values())


def pad_notes(program: dict[str, Any], count: int, spacing: int) -> list[tuple[int, int, float, int]]:
    notes = program["padNoteMap"]["noteForPad"]
    return [(i * spacing, notes[f"value{i}"], 1.0, spacing // 2) for i in range(count)]


def bass_line() -> list[tuple[int, int, float, int]]:
    return [(i * PPQ, pitch, 1.0, PPQ * 3 // 4) for i, pitch in enumerate((36, 36, 43, 41, 36, 48, 43, 41))]


def melody() -> list[tuple[int, int, float, int]]:
    return [(i * PPQ, pitch, 1.0, PPQ // 2) for i, pitch in enumerate((48, 50, 52, 53, 55, 57, 59, 60))]


def own_keygroup(project: Project, rich: Project, name: str, path: Path, root: int, key_track: bool, mono: bool) -> None:
    track = source_track(rich, "LD True Survivor")
    entry = new_entry(rich, path)
    project.data["samples"].append(copy.deepcopy(entry))
    set_keygroup(track["program"], entry, frames(path), root, key_track)
    if mono:
        track["program"]["drum"]["instruments"][0]["monophonic"] = True
        track["program"]["drum"]["monophonic"] = True
    insert_track(project, track, name)


def plain_midi(rich: Project, name: str) -> dict[str, Any]:
    track = source_track(rich, "MIDI Minilogue")
    for route, key in ((track["midiOutputRoute"], "outputPort"), (track["midiInputRoute"], "inputPort")):
        route[key]["deviceName"] = "<none>"
        route[key]["deviceId"] = ""
    track["name"] = name
    return track


def build7() -> None:
    template = MPC / "Spike4 A.xpj"
    rich = load(MPC / "Rataklang - Brassic.xpj")
    amen = MPC / "Spike4 A_[ProjectData]" / "cw_amen01_175.wav"
    bass = RICH / "Bass 808 G .wav"
    long_loop = RICH / "Cymatics - Empire Melody Loop 1 - 100 BPM G Min.wav"
    kick = RICH / "BILLY KICK V10 - A.wav"
    snare = RICH / "SMACK SNARE V10 - A.wav"
    OUT7.mkdir(parents=True, exist_ok=True)
    for old in OUT7.glob("[ADEFGKMSV][0-9][0-9] *"):
        shutil.rmtree(old) if old.is_dir() else old.unlink()

    for name, count, spacing in (("D01 pads16", 16, PPQ), ("D02 pads64", 64, PPQ // 4), ("D03 pads128", 128, PPQ // 8)):
        item = load(template)
        samples = fill_pads(item, rich, count)
        set_notes(item, 0, "Drum 001", pad_notes(item.data["tracks"][0]["program"], count, spacing))
        write7(item, name, samples)

    for name, root, key_track, mono in (
        ("K01 root0", 0, False, False),
        ("K02 root36", 36, False, False),
        ("K03 root36track", 36, True, False),
        ("K04 mono", 36, True, True),
    ):
        item = load(template)
        event = note_template(item)
        own_keygroup(item, rich, "Bass", bass, root, key_track, mono)
        set_notes(item, 0, "Bass", bass_line(), event)
        write7(item, name, [amen, bass])

    item = load(template)
    event = note_template(item)
    insert_track(item, plain_midi(rich, "Synth"), "Synth")
    set_notes(item, 0, "Synth", melody(), event)
    write7(item, "M01 midi", [amen])

    item = load(template)
    add_second_sequence(item)
    set_notes(item, 0, "Drum 001", eighths(36))
    item.data["sequences"][0]["value"]["name"] = "Chorus"
    item.data["sequences"][1]["value"]["name"] = "Verse"
    write7(item, "S01 sections", [amen])

    item = load(template)
    event = note_template(item)
    add_second_sequence(item)
    insert_track(item, copy.deepcopy(item.data["tracks"][0]), "Drum 002")
    set_notes(item, 0, "Drum 002", eighths(36), event)
    set_notes(item, 1, "Drum 002", [(i * PPQ, 36, 1.0, PPQ // 4) for i in range(8)], event)
    write7(item, "S02 tracks", [amen])

    item = load(template)
    value = item.data["sequences"][0]["value"]
    signature = copy.deepcopy(value["timeSignatureTrack"]["timeSignatures"][0])
    signature["beatsPerBar"], signature["barStart"] = 3, 2
    value["timeSignatureTrack"]["timeSignatures"].append(signature)
    set_notes(item, 0, "Drum 001", eighths(36))
    write7(item, "S03 meter", [amen])

    item = load(template)
    fill = copy.deepcopy(item.data["tracks"][0]["program"]["drum"]["instruments"][0])
    program = item.data["tracks"][0]["program"]
    program["drum"]["instruments"][1] = fill
    entry = new_entry(rich, long_loop)
    layer = fill["layersv"][0]
    layer["sampleName"], layer["sampleFile"] = entry["name"], entry["path"]
    layer["sliceInfo"]["End"] = frames(long_loop) - 1
    program["samples"].append(copy.deepcopy(entry))
    item.data["samples"].append(copy.deepcopy(entry))
    set_notes(item, 0, "Drum 001", [(0, 37, 1.0, PPQ * 16)])
    write7(item, "A01 audio", [amen, long_loop])

    source = ROOT / "test-projects" / "exports" / "all-tracks" / "07_CTRL_free.wav"
    mono_file = OUT7 / "mono.wav"
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI24", "-c", "1", str(source), str(mono_file)], check=True
    )
    item = load(template)
    program = item.data["tracks"][0]["program"]
    samples = [amen, source, mono_file]
    for pad, path in ((1, source), (2, mono_file)):
        entry = new_entry(rich, path)
        program["drum"]["instruments"][pad] = copy.deepcopy(program["drum"]["instruments"][0])
        layer = program["drum"]["instruments"][pad]["layersv"][0]
        layer["sampleName"], layer["sampleFile"] = entry["name"], entry["path"]
        layer["sliceInfo"]["End"] = frames(path) - 1
        program["samples"].append(copy.deepcopy(entry))
        item.data["samples"].append(copy.deepcopy(entry))
    set_notes(item, 0, "Drum 001", [(i * PPQ * 4, 36 + i, 1.0, PPQ * 2) for i in range(3)])
    write7(item, "A02 formats", samples)
    mono_file.unlink()

    item = load(template)
    program = item.data["tracks"][0]["program"]
    program["drum"]["instruments"][1] = copy.deepcopy(program["drum"]["instruments"][1])
    sounds = [(rich_entry(rich, kick.name), frames(kick)), (rich_entry(rich, snare.name), frames(snare))]
    set_velocity_layers(program, 1, sounds)
    item.data["samples"].extend(copy.deepcopy(e) for e, _ in sounds)
    set_notes(item, 0, "Drum 001", [(i * PPQ, 37, 0.3 if i % 2 == 0 else 1.0, PPQ // 2) for i in range(8)])
    write7(item, "V01 velocity", [amen, kick, snare])

    item = load(template)
    event = note_template(item)
    insert_track(item, copy.deepcopy(item.data["tracks"][0]), "Muted")
    set_notes(item, 0, "Muted", eighths(36), event)
    muted = item.data["tracks"][1]
    muted["mute"] = True
    muted["program"]["mixable"]["mute"] = True
    insert_track(item, copy.deepcopy(item.data["tracks"][0]), "Clip off")
    set_notes(item, 0, "Clip off", eighths(36), event)
    for note in clip(item, 0, "Clip off")["eventList"]["events"]:
        note["muted"] = True
    write7(item, "M02 mute", [amen])

    item = load(template)
    event = note_template(item)
    own_keygroup(item, rich, "Bass", bass, 36, True, True)
    set_notes(item, 0, "Bass", bass_line(), event)
    item.data["tracks"][0]["program"]["mixable"]["audioRoute"]["destination"] = 2
    item.data["tracks"][1]["program"]["mixable"]["audioRoute"]["destination"] = 2
    write7(item, "G01 merge", [amen, bass])

    item = load(template)
    program = item.data["tracks"][0]["program"]
    entry = new_entry(rich, kick, "NOFILE_DR_Kick_01")
    program["drum"]["instruments"][1] = copy.deepcopy(program["drum"]["instruments"][0])
    layer = program["drum"]["instruments"][1]["layersv"][0]
    layer["sampleName"], layer["sampleFile"] = entry["name"], entry["path"]
    program["samples"].append(copy.deepcopy(entry))
    item.data["samples"].append(copy.deepcopy(entry))
    set_notes(item, 0, "Drum 001", [(i * PPQ, 36 + i % 2, 1.0, PPQ // 2) for i in range(8)])
    write7(item, "E01 missing", [amen])

    item = load(template)
    event = note_template(item)
    samples = fill_pads(item, rich, 16)
    drums = item.data["tracks"][0]
    set_notes(item, 0, "Drum 001", pad_notes(drums["program"], 16, PPQ))
    hands = copy.deepcopy(drums)
    clear_pads(hands["program"])
    insert_track(item, hands, "HANDS")
    item.data["tracks"].remove(hands)
    item.data["tracks"].insert(0, hands)
    own_keygroup(item, rich, "Bass", bass, 36, True, True)
    set_notes(item, 0, "Bass", bass_line(), event)
    insert_track(item, plain_midi(rich, "Synth"), "Synth")
    set_notes(item, 0, "Synth", melody(), event)
    write7(item, "F01 full", [*samples, bass])

    for path in sorted(OUT7.glob("*.xpj")):
        tracks = [t["name"] for t in load(path).data["tracks"] if t["program"]["type"] < 7]
        print(f"{path.name}: {path.stat().st_size} байт, треки {tracks}")


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
    elif sys.argv[1] == "build7":
        build7()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
