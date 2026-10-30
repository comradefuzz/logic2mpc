#!/usr/bin/env python3
"""Разведка проекта Logic для спайка 1. Только чтение, не код продукта.

Смещения взяты как гипотезы из спецификации LogicProFormatWriter
(PROJECTDATA_FORMAT.md, Logic 11.2.2) и подтверждаются сверкой
с контрольным проектом. Результат: docs/spikes.md.

    probe.py summary <project.logicx> [--alt NNN]
    probe.py tags <project.logicx> [--alt NNN]
    probe.py tree <project.logicx> [--alt NNN]
    probe.py regions <project.logicx> [--alt NNN]
    probe.py diff <a.logicx> <b.logicx> [--alt NNN]
    probe.py hash <project.logicx> ...
"""
from __future__ import annotations

import argparse
import hashlib
import plistlib
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

MAGIC = bytes.fromhex("2347c0ab")
ROOT_HEADER = 24
RECORD_HEADER = 36
TAIL = 0xF1
TEMPO_ORIGIN = 38400
REGION_ORIGIN = 34560
PPQ = 960


@dataclass(frozen=True)
class Record:
    offset: int
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
    records = []
    offset = ROOT_HEADER
    while offset < len(data):
        if offset + RECORD_HEADER > len(data):
            raise ValueError(f"обрезанный заголовок на {offset:#x}")
        total = RECORD_HEADER + u32(data, offset + 0x1C)
        if offset + total > len(data):
            raise ValueError(f"запись выходит за файл на {offset:#x}")
        raw = data[offset : offset + total]
        records.append(
            Record(
                offset,
                raw[:4].decode("latin-1"),
                u16(raw, 0x06),
                u32(raw, 0x08),
                u16(raw, 0x12),
                u16(raw, 0x14),
                raw,
            )
        )
        offset += total
    return records


def alternative(project: Path, alt: str | None) -> Path:
    base = project / "Alternatives"
    if alt:
        return base / alt
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


def bars(tick: int, numerator: int = 4, denominator: int = 4) -> float:
    return tick / (PPQ * 4 * numerator / denominator) + 1


def tempo_map(records: list[Record]) -> list[tuple[int, float]]:
    points = []
    for record in records:
        if record.tag != "qSvE" or record.role != 3:
            continue
        body = record.payload
        for offset in range(0, len(body) - 31, 32):
            if body[offset] != 0x60:
                break
            tick = u32(body, offset + 4) - TEMPO_ORIGIN
            points.append((tick, u32(body, offset + 0x10) / 10000))
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
            tick = u32(body, offset + 4) - TEMPO_ORIGIN
            changes.append((tick, body[offset + 0x0C], 2 ** body[offset + 0x0B]))
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
            tick = u32(body, offset + 4) - TEMPO_ORIGIN
            found.append((tick, names.get(u16(body, offset + 0x10))))
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


def channels(records: list[Record]) -> dict[int, tuple[int, str]]:
    """Слот объекта Environment → (вид, имя)."""
    found = {}
    for record in records:
        if record.tag != "ivnE" or len(record.payload) < 0xA0:
            continue
        name = sized_string(record.payload, 0x9E)
        if name:
            found[record.idx >> 16] = (record.payload[0x5A], name)
    return found


def arrange_rows(records: list[Record]) -> list[tuple[int, int, str | None]]:
    """Строки аранжировки: (тип строки, слот канала, имя канала)."""
    names = channels(records)
    rows = [
        r
        for r in records
        if r.tag == "karT" and r.idx == 0x40000 and r.link2 == 0 and len(r.payload) >= 12
    ]
    result = []
    for row in sorted(rows, key=lambda r: r.link1):
        slot = u32(row.payload, 0x08)
        channel = names.get(slot)
        result.append((row.payload[0], slot, channel[1] if channel else None))
    return result


def stack_tree(records: list[Record]) -> list[str]:
    """Глубина в pay+0x0e. Заголовок: следующая строка глубже. Summing: бит 0x40 в pay+0x28."""
    names = channels(records)
    rows = [
        r
        for r in records
        if r.tag == "karT" and r.idx == 0x40000 and r.link2 == 0 and len(r.payload) >= 0x2C
    ]
    rows.sort(key=lambda r: r.link1)
    depths = [u16(r.payload, 0x0E) for r in rows]
    lines = []
    for number, row in enumerate(rows):
        channel = names.get(u32(row.payload, 0x08))
        name = channel[1] if channel else "?"
        header = number + 1 < len(rows) and depths[number + 1] > depths[number]
        if header:
            kind = "summing" if row.payload[0x28] & 0x40 else "folder"
            name = f"[{name}] ({kind})"
        lines.append("  " * depths[number] + name)
    return lines


def audio_regions(records: list[Record]) -> list[str]:
    names = (sized_string(r.payload, 0x4A) for r in records if r.tag == "gRuA")
    return [name for name in names if name]


@dataclass(frozen=True)
class Region:
    kind: str
    name: str | None
    tick: int
    row: int
    length: int | None
    depth: int
    audible: bool


def placements(body: bytes) -> list[int]:
    """Смещения размещений: метки 0x89 и 0x8a отличают их от других событий."""
    found = []
    for offset in range(0, len(body) - 79, 16):
        kind = body[offset]
        if kind in (0x20, 0x24) and body[offset + 0x17] == 0x89 and body[offset + 0x37] == 0x8A:
            found.append(offset)
    return found


def regions(records: list[Record]) -> list[Region]:
    """Обход от корневого списка, папки регионов раскрываются рекурсивно.

    Длина: у MIDI тики из qeSM, у аудио кадры исходника из gRuA.
    """
    lists = {r.idx: r for r in records if r.tag == "qSvE" and r.role == 0x17}
    sequences = {r.idx: r for r in records if r.tag == "qeSM" and r.role == 0x17}
    audio = {(r.idx, u32(r.raw, 0x0C)): r for r in records if r.tag == "gRuA"}
    found: list[Region] = []

    def visit(idx: int, base: int, row: int | None, depth: int, seen: set[int]) -> None:
        if idx in seen or idx not in lists:
            return
        seen = seen | {idx}
        body = lists[idx].payload
        for offset in placements(body):
            tick = base + u32(body, offset + 4) - REGION_ORIGIN
            own_row = row if row is not None else u16(body, offset + 0x14) - 1
            audible = not u32(body, offset + 0x0C) & 0x10
            if body[offset] == 0x24:
                file_index = u32(body, offset + 0x2C)
                number = u32(body, offset + 0x28)
                target = audio.get((file_index << 16, number << 16))
                name = sized_string(target.payload, 0x4A) if target else None
                length = u32(target.payload, 0x16) if target else None
                found.append(Region("audio", name, tick, own_row, length, depth, audible))
                continue
            child = u32(body, offset + 0x20) << 16
            sequence = sequences.get(child)
            name = sized_string(sequence.payload, 0x10) if sequence else None
            if name == "*Automation":
                continue
            if child in lists and placements(lists[child].payload):
                visit(child, tick, own_row, depth + 1, seen)
                continue
            length = u32(sequence.payload, 0x56) if sequence else None
            found.append(Region("midi", name, tick, own_row, length, depth, audible))

    visit(0x40000, 0, None, 0, set())
    return found


def load(project: Path, alt: str | None) -> tuple[Path, bytes]:
    folder = alternative(project, alt)
    return folder, (folder / "ProjectData").read_bytes()


def cmd_summary(args: argparse.Namespace) -> None:
    folder, data = load(args.project, args.alt)
    records = walk(data)
    meta = plistlib.loads((folder / "MetaData.plist").read_bytes())
    info = plistlib.loads((args.project / "Resources/ProjectInformation.plist").read_bytes())
    print(f"проект: {args.project.name}, альтернатива {folder.name}")
    print(f"Logic: {info.get('LastSavedFrom')}, версия файла {data[4:6].hex()}")
    print(f"варианты: {info.get('VariantNames')}")
    print(
        f"MetaData: {meta.get('BeatsPerMinute')} BPM, "
        f"{meta.get('SongSignatureNumerator')}/{meta.get('SongSignatureDenominator')}, "
        f"{meta.get('SongKey')} {meta.get('SongGenderKey')}, {meta.get('SampleRate')} Гц, "
        f"дорожек {meta.get('NumberOfTracks')}"
    )
    print(f"записей: {len(records)}, разбор до конца файла: да")
    print(f"темп: {[(round(bars(t), 2), bpm) for t, bpm in tempo_map(records)][:20]}")
    print(f"размер: {meter_map(records)[:20]}")
    found = markers(records)
    print(f"маркеры ({len(found)}): {[(round(bars(t), 2), n) for t, n in found][:30]}")
    rows = arrange_rows(records)
    print(f"строки аранжировки ({len(rows)}): {rows[:args.limit]}")
    kinds = Counter(kind for kind, _ in channels(records).values())
    print(f"объекты Environment по видам: {dict(kinds)}")
    names = audio_regions(records)
    print(f"аудиорегионы gRuA ({len(names)}): {names[:args.limit]}")
    print(f"размещения: {Counter(r.kind for r in regions(records))}")


def cmd_tags(args: argparse.Namespace) -> None:
    _, data = load(args.project, args.alt)
    counts = Counter((r.tag, r.role) for r in walk(data))
    for (tag, role), count in sorted(counts.items()):
        print(f"{tag} role={role:#06x} {count}")


def cmd_tree(args: argparse.Namespace) -> None:
    _, data = load(args.project, args.alt)
    print("\n".join(stack_tree(walk(data))))


def cmd_regions(args: argparse.Namespace) -> None:
    _, data = load(args.project, args.alt)
    records = walk(data)
    rows = arrange_rows(records)
    for region in sorted(regions(records), key=lambda r: (r.row, r.tick)):
        track = rows[region.row][2] if 0 <= region.row < len(rows) else f"?{region.row}"
        print(
            f"{track} | {region.kind} | {region.name} | такт {bars(region.tick):.2f} "
            f"| длина {region.length} | глубина {region.depth} | слышен {region.audible}"
        )


def keyed(records: list[Record]) -> dict[tuple[str, int, int, int, int], Record]:
    seen: Counter[tuple[str, int, int, int]] = Counter()
    result = {}
    for record in records:
        key = (record.tag, record.role, record.idx, record.link1)
        result[(*key, seen[key])] = record
        seen[key] += 1
    return result


def cmd_diff(args: argparse.Namespace) -> None:
    left = keyed(walk(load(args.a, args.alt)[1]))
    right = keyed(walk(load(args.b, args.alt)[1]))
    print(f"записей: {len(left)} и {len(right)}")
    for key in left.keys() - right.keys():
        print(f"только слева: {key}")
    for key in right.keys() - left.keys():
        print(f"только справа: {key}")
    for key in left.keys() & right.keys():
        a, b = left[key].raw, right[key].raw
        if a == b:
            continue
        changed = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        print(f"{key}: размер {len(a)}→{len(b)}, байтов {len(changed)}, первые {changed[:12]}")


def cmd_hash(args: argparse.Namespace) -> None:
    for project in args.projects:
        for path in sorted(project.glob("Alternatives/*/ProjectData")):
            print(hashlib.sha256(path.read_bytes()).hexdigest(), path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("project", type=Path)
    summary.add_argument("--alt")
    summary.add_argument("--limit", type=int, default=40)
    summary.set_defaults(run=cmd_summary)
    tags = commands.add_parser("tags")
    tags.add_argument("project", type=Path)
    tags.add_argument("--alt")
    tags.set_defaults(run=cmd_tags)
    region_list = commands.add_parser("regions")
    region_list.add_argument("project", type=Path)
    region_list.add_argument("--alt")
    region_list.set_defaults(run=cmd_regions)
    tree = commands.add_parser("tree")
    tree.add_argument("project", type=Path)
    tree.add_argument("--alt")
    tree.set_defaults(run=cmd_tree)
    diff = commands.add_parser("diff")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.add_argument("--alt")
    diff.set_defaults(run=cmd_diff)
    hashes = commands.add_parser("hash")
    hashes.add_argument("projects", type=Path, nargs="+")
    hashes.set_defaults(run=cmd_hash)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
