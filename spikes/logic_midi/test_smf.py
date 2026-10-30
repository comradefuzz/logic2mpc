"""Разбор SMF на синтетическом файле с известной структурой."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smf  # noqa: E402


def chunk(tag: bytes, body: bytes) -> bytes:
    return tag + struct.pack(">I", len(body)) + body


def build() -> bytes:
    tempo = int(60_000_000 / 120).to_bytes(3, "big")
    conductor = (
        b"\x00\xff\x58\x04\x04\x02\x18\x08"
        + b"\x00\xff\x51\x03"
        + tempo
        + b"\x83\x60\xff\x06\x03ABC"  # 480 тиков
        + b"\x00\xff\x2f\x00"
    )
    notes = (
        b"\x00\xff\x03\x03RGN"
        + b"\x00\xff\x04\x03TRK"
        + b"\x83\x60\x90\x3c\x64"  # нота 60 на тике 480
        + b"\x83\x60\x3e\x50"  # бегущий статус: нота 62 на тике 960
        + b"\x83\x60\x80\x3c\x00"  # конец ноты 60 на тике 1440
        + b"\x00\x90\x3e\x00"  # конец ноты 62 через velocity 0
        + b"\x00\xff\x2f\x00"
    )
    header = chunk(b"MThd", struct.pack(">HHH", 1, 2, 480))
    return header + chunk(b"MTrk", conductor) + chunk(b"MTrk", notes)


def test_header_and_conductor() -> None:
    song = smf.parse(build())
    assert (song.format, song.ppq) == (1, 480)
    assert song.tempo == [(0, 120.0)]
    assert song.meter == [(0, 4, 4)]
    assert song.markers == [(480, "ABC")]


def test_track_names_and_notes() -> None:
    track = smf.parse(build()).tracks[1]
    assert (track.name, track.instrument) == ("RGN", "TRK")
    assert track.notes == [
        smf.Note(tick=480, pitch=60, velocity=100, length=960),
        smf.Note(tick=960, pitch=62, velocity=80, length=480),
    ]
