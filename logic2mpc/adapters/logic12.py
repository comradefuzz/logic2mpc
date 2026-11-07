"""Чтение проекта Logic 12 (версия файла ProjectData 0x09D1).

Полная копия адаптера 10.8.1 (`logic.py`), который не меняется: правило «адаптер на версию формата» (CLAUDE.md).
Основание: спайк S-027, реквесты LOGIC-R-010…013 к docs/formats/logic/. Сравнение адаптеров: docs/adapters.md.
"""
from __future__ import annotations

import plistlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.model import BAR, AudioRegion, MidiRegion, Note, Track

MAGIC = bytes.fromhex("2347c0ab")
VERSIONS = (0x09D1,)
ROOT_HEADER = 24
RECORD_HEADER = 36
TEMPO_ORIGIN = 38400
REGION_ORIGIN = 34560
LOOP = 0x200
PPQ = 960


@dataclass(frozen=True)
class Song:
    bpm: float
    sr: int
    tracks: list[Track]
    markers: list[tuple[int, str | None]]
    notes_extended: int
    notes_outside: int


@dataclass(frozen=True)
class Record:
    tag: str
    role: int
    idx: int
    link1: int
    link2: int
    raw: bytes

    @property
    def payload(self) -> bytes:
        return self.raw[RECORD_HEADER:]


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def walk(data: bytes) -> list[Record]:
    if data[:4] != MAGIC:
        raise ValueError(f"нет сигнатуры: {data[:4].hex()}")
    if u16(data, 4) not in VERSIONS:
        raise ValueError(f"неизвестная версия файла {u16(data, 4):#06x}, чтение не проверено")
    records = []
    offset = ROOT_HEADER
    while offset < len(data):
        if offset + RECORD_HEADER > len(data):
            raise ValueError(f"обрезанный заголовок на {offset:#x}")
        total = RECORD_HEADER + u32(data, offset + 0x1C)
        if offset + total > len(data):
            raise ValueError(f"запись выходит за файл на {offset:#x}")
        raw = data[offset : offset + total]
        records.append(Record(raw[:4].decode("latin-1"), u16(raw, 0x06), u32(raw, 0x08), u16(raw, 0x12), u16(raw, 0x14), raw))
        offset += total
    return records


def alternative(project: Path) -> Path:
    base = project / "Alternatives"
    found = sorted(p for p in base.iterdir() if (p / "ProjectData").is_file())
    if not found:
        raise FileNotFoundError(f"нет ProjectData в {base}")
    info = plistlib.loads((project / "Resources/ProjectInformation.plist").read_bytes())
    if "ActiveVariant" not in info:
        return found[-1]
    active = base / f"{info['ActiveVariant']:03d}"
    if active not in found:
        raise FileNotFoundError(f"нет активной альтернативы {active}")
    return active


def tempo_map(records: list[Record]) -> list[tuple[int, float]]:
    points = []
    for record in records:
        if record.tag != "qSvE" or record.role != 3:
            continue
        body = record.payload
        for offset in range(0, len(body) - 31, 32):
            if body[offset] != 0x60:
                break
            points.append((u32(body, offset + 4) - TEMPO_ORIGIN, u32(body, offset + 0x10) / 10000))
    return points


def meter_map(records: list[Record]) -> list[tuple[int, int, int]]:
    changes = []
    for record in records:
        if record.tag != "qSvE" or record.role != 1:
            continue
        body = record.payload
        if len(body) < 96:
            continue
        changes.append((0, body[0x0C], 2 ** body[0x0B]))
        for offset in range(80, len(body) - 47, 48):
            if body[offset] != 0x30:
                break
            changes.append((u32(body, offset + 4) - TEMPO_ORIGIN, body[offset + 0x0C], 2 ** body[offset + 0x0B]))
    return changes


def rtf_text(payload: bytes) -> str | None:
    start = payload.find(b"{\\rtf")
    if start < 0:
        return None
    rtf = payload[start:].split(b"\x00", 1)[0].decode("latin-1")
    match = re.search(r"\\cf\d+ (.*)}\s*$", rtf, re.DOTALL)
    return match.group(1).strip() if match else None


def markers(records: list[Record]) -> list[tuple[int, str | None]]:
    names = {}
    for record in records:
        if record.tag == "qSxT":
            text = rtf_text(record.payload)
            if text is not None:
                names[u16(record.raw, 0x0A)] = text
    found = []
    for record in records:
        if record.tag != "qSvE" or not record.payload.startswith(b"\x12\0\0\0"):
            continue
        body = record.payload
        for offset in range(0, len(body) - 47, 48):
            if body[offset] != 0x12:
                break
            found.append((u32(body, offset + 4) - TEMPO_ORIGIN, names.get(u16(body, offset + 0x10))))
    return found


def sized_string(data: bytes, offset: int) -> str | None:
    if offset + 2 > len(data):
        return None
    length = u16(data, offset)
    raw = data[offset + 2 : offset + 2 + length]
    if not 0 < length <= 255 or len(raw) != length:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text.isprintable() else None


def channels(records: list[Record]) -> dict[int, str]:
    found = {}
    for record in records:
        if record.tag != "ivnE" or len(record.payload) < 0xA0:
            continue
        name = sized_string(record.payload, 0x9E)
        if name:
            found[record.idx >> 16] = name
    return found


@dataclass(frozen=True)
class Row:
    number: int
    name: str
    depth: int
    header: bool


def rows_of(records: list[Record]) -> list[Row]:
    """Глубина в pay+0x0e. Заголовок стека: следующая строка глубже."""
    names = channels(records)
    rows = [r for r in records if r.tag == "karT" and r.idx == 0x40000 and r.link2 == 0 and len(r.payload) >= 0x2C]
    rows.sort(key=lambda r: r.link1)
    depths = [u16(r.payload, 0x0E) for r in rows]
    found = []
    for number, row in enumerate(rows):
        name = names.get(u32(row.payload, 0x08)) or "?"
        header = number + 1 < len(rows) and depths[number + 1] > depths[number]
        found.append(Row(number, name, depths[number], header))
    return found


def placements(body: bytes) -> list[int]:
    """Смещения размещений: метки 0x89 и 0x8a отличают их от других событий."""
    found = []
    for offset in range(0, len(body) - 79, 16):
        if body[offset] in (0x20, 0x24) and body[offset + 0x17] == 0x89 and body[offset + 0x37] == 0x8A:
            found.append(offset)
    return found


def midi_length(payload: bytes) -> int:
    """Длина в тиках. Поля за именем сдвигаются: имя выравнивается по чётной длине."""
    name_end = 0x12 + (u16(payload, 0x10) + 1 & ~1)
    return u32(payload, name_end + 0x3C)


def loop_passes(length: int, flags: int, total: int) -> list[int]:
    if not flags & LOOP or length <= 0:
        return [0]
    return list(range(0, total, length))


def audio_regions(records: list[Record], bpm: float, sr: int) -> dict[int, list[AudioRegion]]:
    """Аудиорегионы по строкам: папки с Loop развёрнуты, Mute и длина папки учтены.

    Длина берётся из gRuA в кадрах исходника, годится только для выбора длины лупа, см. LOGIC-044.
    """
    lists = {r.idx: r for r in records if r.tag == "qSvE" and r.role == 0x17}
    sequences = {r.idx: r for r in records if r.tag == "qeSM" and r.role == 0x17}
    audio = {(r.idx, u32(r.raw, 0x0C)): r for r in records if r.tag == "gRuA"}
    found: dict[int, list[AudioRegion]] = {}

    def visit(idx: int, base: int, row: int | None, limit: int | None, muted: bool, seen: set[int]) -> None:
        if idx in seen or idx not in lists:
            return
        seen = seen | {idx}
        body = lists[idx].payload
        for offset in placements(body):
            flags = u32(body, offset + 0x0C)
            relative = u32(body, offset + 4) - REGION_ORIGIN
            if limit is not None and relative >= limit:
                continue
            off = muted or bool(flags & 1)
            tick = base + relative
            own_row = row if row is not None else u16(body, offset + 0x14) - 1
            total = u32(body, offset + 0x1C)
            if body[offset] == 0x24:
                target = audio.get((u32(body, offset + 0x2C) << 16, u32(body, offset + 0x28) << 16))
                frames = u32(target.payload, 0x16) if target else None
                length = round(frames * PPQ * bpm / (60 * sr)) if frames else None
                # Номер файла и фрагмент файла, см. LOGIC-R-009.
                source = u32(body, offset + 0x2C)
                start = u32(target.payload, 0x06) if target else None
                region = AudioRegion(tick, tick + total if flags & LOOP else None, length, off, source, start, frames)
                found.setdefault(own_row, []).append(region)
                continue
            child = u32(body, offset + 0x20) << 16
            sequence = sequences.get(child)
            if sequence is None or child not in lists or not placements(lists[child].payload):
                continue
            size = midi_length(sequence.payload)
            end = total if flags & LOOP else size
            for start in loop_passes(size, flags, total):
                room = min(size, end - start)
                if limit is not None:
                    room = min(room, limit - relative - start)
                if room > 0:
                    visit(child, tick + start, own_row, room, off, seen)

    visit(0x40000, 0, None, None, False, set())
    return {row: sorted(items, key=lambda r: r.tick) for row, items in found.items()}


def sequence_notes(body: bytes) -> tuple[list[Note], int]:
    """Ноты списка событий от начала региона и число расширенных, см. LOGIC-062."""
    notes = []
    extended = 0
    for offset in range(0, len(body) - 31, 16):
        if body[offset] & 0xF0 != 0x90 or body[offset + 1] not in (0, 0x40):
            continue
        if body[offset + 0x17] != 0x89:
            continue
        extended += body[offset + 1] == 0x40
        notes.append(Note(u32(body, offset + 4) - TEMPO_ORIGIN, body[offset + 0x0C], body[offset + 0x0B], u32(body, offset + 0x1C)))
    return notes, extended


def midi_regions(records: list[Record]) -> tuple[dict[int, list[MidiRegion]], int, int]:
    """Ноты MIDI-регионов, папки раскрываются. Выключенные не отбрасываются.

    Возвращает ещё число расширенных нот и нот за границами региона: их смысл не установлен,
    они переносятся как есть и попадают в отчёт. См. LOGIC-062, LOGIC-063.
    """
    lists = {r.idx: r for r in records if r.tag == "qSvE" and r.role == 0x17}
    sequences = {r.idx: r for r in records if r.tag == "qeSM" and r.role == 0x17}
    found: dict[int, list[MidiRegion]] = {}
    counts = [0, 0]

    def visit(idx: int, base: int, row: int | None, limit: int | None, parent_muted: bool, seen: set[int]) -> None:
        if idx in seen or idx not in lists:
            return
        seen = seen | {idx}
        body = lists[idx].payload
        for offset in placements(body):
            if body[offset] != 0x20:
                continue
            flags = u32(body, offset + 0x0C)
            child = u32(body, offset + 0x20) << 16
            relative = u32(body, offset + 4) - REGION_ORIGIN
            if child not in lists or child not in sequences:
                continue
            if limit is not None and relative >= limit:
                continue
            tick = base + relative
            own_row = row if row is not None else u16(body, offset + 0x14) - 1
            muted = parent_muted or bool(flags & 1)
            length = midi_length(sequences[child].payload)
            total = u32(body, offset + 0x1C)
            if placements(lists[child].payload):
                end = total if flags & LOOP else length
                for start in loop_passes(length, flags, total):
                    room = min(length, end - start)
                    if limit is not None:
                        room = min(room, limit - relative - start)
                    if room > 0:
                        visit(child, tick + start, own_row, room, muted, seen)
                continue
            source = u32(body, offset + 0x08) << 16
            if source == 0 or source not in lists:
                source = child
            transpose = struct.unpack_from("<b", body, offset + 0x35)[0]
            raw, extended = sequence_notes(lists[source].payload)
            notes = [
                Note(n.tick, n.pitch + transpose, n.velocity, n.length)
                for n in raw
                if limit is None or relative + n.tick < limit
            ]
            counts[0] += extended
            counts[1] += sum(1 for n in notes if n.tick < 0 or n.tick >= length)
            found.setdefault(own_row, []).append(MidiRegion(tick, notes, muted))
            for start in loop_passes(length, flags, total)[1:]:
                end = total - start if limit is None else min(total - start, limit - relative - start)
                visible = [n for n in notes if n.tick < end]
                if visible:
                    found[own_row].append(MidiRegion(tick + start, visible, muted))

    visit(0x40000, 0, None, None, False, set())
    return found, counts[0], counts[1]


def read_project(project: Path) -> Song:
    folder = alternative(project)
    data = (folder / "ProjectData").read_bytes()
    records = walk(data)
    meta = plistlib.loads((folder / "MetaData.plist").read_bytes())
    tempo = {bpm for _, bpm in tempo_map(records)}
    if len(tempo) != 1:
        raise ValueError(f"первая версия рассчитана на постоянный темп, найдено {sorted(tempo)}")
    meters = {(top, low) for _, top, low in meter_map(records)}
    if meters - {(4, 4)}:
        raise ValueError(f"первая версия рассчитана на размер 4/4, найдено {sorted(meters)}")
    bpm = tempo.pop()
    sr = int(meta["SampleRate"])
    audio = audio_regions(records, bpm, sr)
    midi, extended, outside = midi_regions(records)
    tracks = []
    group: str | None = None
    for row in rows_of(records):
        if row.depth == 0:
            group = row.name if row.header else None
        if row.header:
            continue  # файл стека задвоит дочерние дорожки, AN-002
        tracks.append(Track(row.number, row.name, group, midi.get(row.number, []), audio.get(row.number, [])))
    return Song(bpm, sr, tracks, sorted(markers(records), key=lambda m: m[0]), extended, outside)


__all__ = ["BAR", "Song", "read_project"]
