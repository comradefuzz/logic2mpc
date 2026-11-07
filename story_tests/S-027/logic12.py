"""Помощники спайка S-027: чтение ProjectData Logic 12 (0x09D1) и MIDI без проверки версии адаптера 10.8.1.

Продукт не меняется: список версий адаптера подменяется только в этом процессе.
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

from logic2mpc.adapters import logic as L

ROOT = Path(__file__).resolve().parents[2]
NEW_ALT = ROOT / "test-projects/reference/L12/Spike Control copy.logicx/Alternatives/000"
NEW_OLD_ALT = ROOT / "test-projects/reference/L12/Spike Control copy.logicx/Alternatives/001"
OLD_ALT = ROOT / "test-projects/Spike Control.logicx/Alternatives/000"
OLD_ALT_1 = ROOT / "test-projects/Spike Control.logicx/Alternatives/001"
NEW_MID = ROOT / "test-projects/reference/L12/Spike Control copy.mid"
OLD_MID = ROOT / "test-projects/Spike Control.mid"
VERSION_NEW, VERSION_OLD = 0x09D1, 0x09CB


def load(alt: Path) -> list[L.Record]:
    saved = L.VERSIONS
    L.VERSIONS = tuple(set(saved) | {VERSION_NEW})
    try:
        return L.walk((alt / "ProjectData").read_bytes())
    finally:
        L.VERSIONS = saved


def version(alt: Path) -> int:
    return L.u16((alt / "ProjectData").read_bytes(), 4)


def profile(records: list[L.Record]) -> Counter:
    return Counter((r.tag, r.role) for r in records)


def read_all(records: list[L.Record], bpm: float = 100.0, sr: int = 48000) -> dict:
    mid, ext, outside = L.midi_regions(records)
    return {
        "tempo": L.tempo_map(records),
        "meter": L.meter_map(records),
        "markers": L.markers(records),
        "rows": [(r.number, r.name, r.depth, r.header) for r in L.rows_of(records)],
        "audio": {k: list(v) for k, v in L.audio_regions(records, bpm, sr).items()},
        "midi": {k: list(v) for k, v in mid.items()},
        "extended": ext,
        "outside": outside,
    }


def _vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = value << 7 | byte & 0x7F
        if not byte & 0x80:
            return value, pos


def midi_tracks(path: Path) -> list[dict]:
    """По каждой дорожке SMF: имя, абсолютное время End of Track и последнего note off (тики файла)."""
    data = path.read_bytes()
    ppq = struct.unpack(">H", data[12:14])[0]
    pos, out = 14, []
    while pos < len(data):
        size = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        body, pos = data[pos + 8 : pos + 8 + size], pos + 8 + size
        i = absolute = last_off = 0
        name, running = "", 0
        while i < len(body):
            delta, i = _vlq(body, i)
            absolute += delta
            status = body[i]
            if status == 0xFF:
                kind = body[i + 1]
                length, j = _vlq(body, i + 2)
                if kind == 0x03:
                    name = body[j : j + length].decode("latin-1")
                if kind == 0x2F:
                    out.append({"name": name, "eot": absolute, "last_off": last_off, "ppq": ppq})
                    break
                i = j + length
                continue
            if status in (0xF0, 0xF7):
                length, j = _vlq(body, i + 1)
                i = j + length
                continue
            if status & 0x80:
                running, i = status, i + 1
            kind = running & 0xF0
            first = body[i]
            second = body[i + 1] if kind not in (0xC0, 0xD0) else 0
            if kind == 0x80 or (kind == 0x90 and second == 0):
                last_off = absolute
            i += 1 if kind in (0xC0, 0xD0) else 2
            del first
    return out
