"""Папки регионов и Loop на синтетических записях: LOGIC-047, LOGIC-055."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe  # noqa: E402

BAR = 3840
ROOT = 0x40000
FOLDER = 0x50000


def placement(kind: int, tick: int, flags: int = 0, total: int = 0, child: int = 0, row: int = 1) -> bytes:
    body = bytearray(80)
    body[0] = kind
    struct.pack_into("<I", body, 4, tick + probe.REGION_ORIGIN)
    struct.pack_into("<I", body, 0x0C, flags)
    struct.pack_into("<H", body, 0x14, row + 1)
    body[0x17] = 0x89
    struct.pack_into("<I", body, 0x1C, total)
    struct.pack_into("<I", body, 0x20, child >> 16)
    body[0x37] = 0x8A
    return bytes(body)


def record(tag: str, idx: int, payload: bytes) -> probe.Record:
    return probe.Record(0, tag, 0x17, idx, 0, 0, bytes(probe.RECORD_HEADER) + payload)


def sequence(length: int) -> bytes:
    name = b"F"
    head = bytes(0x10) + struct.pack("<H", len(name)) + name + b"\0"
    return head + bytes(0x3C) + struct.pack("<I", length) + bytes(8)


def project(top: list[bytes], children: list[bytes], folder_length: int) -> list[probe.Record]:
    return [
        record("qSvE", ROOT, b"".join(top)),
        record("qSvE", FOLDER, b"".join(children)),
        record("qeSM", FOLDER, sequence(folder_length)),
    ]


def ticks(records: list[probe.Record]) -> list[int]:
    return [p.tick for p in probe.audio_positions(records)]


def test_folder_mute_silences_clean_children() -> None:
    children = [placement(0x24, 0), placement(0x24, BAR)]
    records = project([placement(0x20, 0, flags=1, child=FOLDER)], children, 4 * BAR)
    assert ticks(records) == []
    assert not any(r.audible for r in probe.regions(records))


def test_child_muted_inside_folder() -> None:
    children = [placement(0x24, 0), placement(0x24, BAR, flags=1)]
    records = project([placement(0x20, 0, child=FOLDER)], children, 4 * BAR)
    assert ticks(records) == [0]


def test_folder_length_cuts_children() -> None:
    children = [placement(0x24, 0), placement(0x24, 3 * BAR)]
    records = project([placement(0x20, 0, child=FOLDER)], children, 2 * BAR)
    assert ticks(records) == [0]
    assert [r.audible for r in probe.regions(records)] == [True, False]


def test_folder_loop_ends_at_total_length() -> None:
    children = [placement(0x24, 0), placement(0x24, BAR)]
    top = [placement(0x20, 0, flags=0x1200, total=6 * BAR, child=FOLDER)]
    records = project(top, children, 4 * BAR)
    assert ticks(records) == [0, BAR, 4 * BAR, 5 * BAR]


def test_loop_flag_without_0x1000() -> None:
    children = [placement(0x24, 0)]
    top = [placement(0x20, 0, flags=0x200, total=8 * BAR, child=FOLDER)]
    records = project(top, children, 4 * BAR)
    assert ticks(records) == [0, 4 * BAR]


def test_flag_0x1000_alone_is_not_loop() -> None:
    children = [placement(0x24, 0)]
    top = [placement(0x20, 0, flags=0x1000, total=8 * BAR, child=FOLDER)]
    records = project(top, children, 4 * BAR)
    assert ticks(records) == [0]


def test_audio_loop_keeps_end() -> None:
    records = project([placement(0x24, BAR, flags=0x1200, total=16 * BAR)], [], BAR)
    found = probe.audio_positions(records)
    assert [(p.tick, p.loop_end) for p in found] == [(BAR, 17 * BAR)]


def note(tick: int, pitch: int) -> bytes:
    body = bytearray(32)
    body[0] = 0x90
    struct.pack_into("<I", body, 4, tick + probe.TEMPO_ORIGIN)
    body[0x0B], body[0x0C] = 100, pitch
    body[0x17] = 0x89
    struct.pack_into("<I", body, 0x1C, 240)
    return bytes(body)


def midi_folder(flags: int = 0, total: int = 0) -> list[probe.Record]:
    inner = 0x60000
    top = [placement(0x20, BAR, flags=flags, total=total, child=FOLDER)]
    records = project(top, [placement(0x20, 0, child=inner)], BAR)
    return records + [
        record("qSvE", inner, note(0, 40) + note(2 * BAR, 41)),
        record("qeSM", inner, sequence(4 * BAR)),
    ]


def test_notes_inside_folder_are_read_and_cut_by_folder() -> None:
    found = probe.region_notes(midi_folder())
    assert [(r.tick, [n.pitch for n in r.notes]) for r in found] == [(BAR, [40])]


def test_notes_inside_muted_folder_stay_marked() -> None:
    found = probe.region_notes(midi_folder(flags=1))
    assert [r.muted for r in found] == [True]


def test_notes_inside_looped_folder_repeat() -> None:
    found = probe.region_notes(midi_folder(flags=0x200, total=2 * BAR))
    assert [r.tick for r in found] == [BAR, 2 * BAR]


def looped_midi() -> list[probe.Record]:
    inner = 0x60000
    return [
        record("qSvE", ROOT, placement(0x20, 0, flags=0x1200, total=3 * BAR, child=inner)),
        record("qSvE", inner, note(0, 40) + note(int(1.5 * BAR), 41)),
        record("qeSM", inner, sequence(2 * BAR)),
    ]


def test_notes_of_cut_loop() -> None:
    found = probe.region_notes(looped_midi())
    assert [(r.tick, [n.pitch for n in r.notes]) for r in found] == [(0, [40, 41]), (2 * BAR, [40])]


def test_loop_inside_folder_stops_at_folder_end() -> None:
    inner = 0x60000
    top = [placement(0x20, 0, child=FOLDER)]
    child = [placement(0x20, 0, flags=0x1200, total=8 * BAR, child=inner)]
    records = project(top, child, 3 * BAR) + [
        record("qSvE", inner, note(0, 40) + note(int(1.5 * BAR), 41)),
        record("qeSM", inner, sequence(2 * BAR)),
    ]
    found = probe.region_notes(records)
    assert [(r.tick, [n.pitch for n in r.notes]) for r in found] == [(0, [40, 41]), (2 * BAR, [40])]


def test_nested_folder_keeps_outer_limit() -> None:
    inner = 0x60000
    top = [placement(0x20, 0, child=FOLDER)]
    middle = [placement(0x20, 0, child=inner)]
    records = project(top, middle, 2 * BAR) + [
        record("qSvE", inner, placement(0x24, 0) + placement(0x24, 3 * BAR)),
        record("qeSM", inner, sequence(4 * BAR)),
    ]
    assert ticks(records) == [0]
    assert [r.audible for r in probe.regions(records)] == [True, False]


def test_midi_loop_has_no_extra_pass() -> None:
    assert probe.loop_passes(2 * BAR, 0x1600, 6 * BAR) == [0, 2 * BAR, 4 * BAR]
    assert probe.loop_passes(2 * BAR, 0x400, 6 * BAR) == [0]
