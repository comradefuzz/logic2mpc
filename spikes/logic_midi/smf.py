#!/usr/bin/env python3
"""Разбор Standard MIDI File для спайка 3. Только чтение, не код продукта.

    smf.py <файл.mid>
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Note:
    tick: int
    pitch: int
    velocity: int
    length: int


@dataclass
class Track:
    name: str | None = None
    instrument: str | None = None
    notes: list[Note] = field(default_factory=list)


@dataclass
class Song:
    format: int
    ppq: int
    tempo: list[tuple[int, float]] = field(default_factory=list)
    meter: list[tuple[int, int, int]] = field(default_factory=list)
    markers: list[tuple[int, str]] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)


def read_varlen(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = value << 7 | byte & 0x7F
        if not byte & 0x80:
            return value, offset


def parse_track(data: bytes, song: Song) -> Track:
    track = Track()
    offset = tick = status = 0
    started: dict[tuple[int, int], list[tuple[int, int]]] = {}
    while offset < len(data):
        delta, offset = read_varlen(data, offset)
        tick += delta
        first = data[offset]
        if first == 0xFF:
            kind = data[offset + 1]
            length, offset = read_varlen(data, offset + 2)
            body = data[offset : offset + length]
            offset += length
            if kind == 0x51:
                song.tempo.append((tick, round(60_000_000 / int.from_bytes(body, "big"), 2)))
            elif kind == 0x58:
                song.meter.append((tick, body[0], 2 ** body[1]))
            elif kind == 0x06:
                song.markers.append((tick, body.decode("utf-8", "replace")))
            elif kind == 0x03:
                track.name = body.decode("utf-8", "replace")
            elif kind == 0x04:
                track.instrument = body.decode("utf-8", "replace")
            continue
        if first in (0xF0, 0xF7):
            length, offset = read_varlen(data, offset + 1)
            offset += length
            continue
        if first & 0x80:
            status = first
            offset += 1
        high = status & 0xF0
        if high in (0xC0, 0xD0):
            offset += 1
            continue
        one, two = data[offset], data[offset + 1]
        offset += 2
        key = (status & 0x0F, one)
        if high == 0x90 and two > 0:
            started.setdefault(key, []).append((tick, two))
        elif high in (0x80, 0x90) and started.get(key):
            begin, velocity = started[key].pop(0)
            track.notes.append(Note(begin, one, velocity, tick - begin))
    track.notes.sort(key=lambda n: (n.tick, n.pitch))
    return track


def parse(data: bytes) -> Song:
    if data[:4] != b"MThd":
        raise ValueError("нет заголовка MThd")
    size = struct.unpack(">I", data[4:8])[0]
    song_format, count, ppq = struct.unpack(">HHH", data[8:14])
    song = Song(song_format, ppq)
    offset = 8 + size
    for _ in range(count):
        length = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        song.tracks.append(parse_track(data[offset + 8 : offset + 8 + length], song))
        offset += 8 + length
    return song


def main() -> None:
    song = parse(Path(sys.argv[1]).read_bytes())
    print(f"формат {song.format}, {song.ppq} PPQ, дорожек {len(song.tracks)}")
    print(f"темп {song.tempo}\nразмер {song.meter}\nмаркеры {song.markers}")
    for number, track in enumerate(song.tracks):
        print(f"{number}: {track.instrument} / {track.name}, нот {len(track.notes)}")


if __name__ == "__main__":
    main()
