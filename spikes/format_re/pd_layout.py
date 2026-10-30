#!/usr/bin/env python3
"""Перепись записей ProjectData всех образцов из test-projects. Только чтение.

    pd_layout.py          заголовок файла, теги и роли
    pd_layout.py TAG      разметка payload тега по байтам, первые LIMIT байт
    pd_layout.py --all    заголовок записи и разметка всех тегов
    pd_layout.py --pair A B   записи, различающиеся между двумя файлами ProjectData
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 0x2000
sys.path.insert(0, str(ROOT / "spikes" / "logic_read"))
import probe  # noqa: E402


def files() -> list[Path]:
    return sorted((ROOT / "test-projects").rglob("ProjectData"))


def records() -> list[tuple[Path, probe.Record]]:
    return [(path, r) for path in files() for r in probe.walk(path.read_bytes())]


def census() -> None:
    for path in files():
        data = path.read_bytes()
        declared = probe.u32(data, 0x10)
        print(data[:24].hex(), "size-24==@10:", declared == len(data) - 24, path.parts[-4][:30])
    tags: dict[tuple[str, int], list[int]] = defaultdict(list)
    for _, r in records():
        tags[(r.tag, r.role)].append(len(r.payload))
    for (tag, role), sizes in sorted(tags.items()):
        print(f"{tag} {tag[::-1]} role={role:#06x} n={len(sizes)} size={min(sizes)}..{max(sizes)} sizes={len(set(sizes))}")


def bytes_table(rows: list[bytes]) -> None:
    size = max((len(p) for p in rows), default=0)
    for offset in range(min(size, LIMIT)):
        values = Counter(p[offset] for p in rows if len(p) > offset)
        common = " ".join(f"{k:02x}×{v}" for k, v in values.most_common(4))
        print(f"+{offset:#05x} n={sum(values.values())} distinct={len(values)} {common}")


def layout(tag: str) -> None:
    payloads = [r.payload for _, r in records() if r.tag == tag]
    print("#", tag, tag[::-1], "записей", len(payloads), "размеры", Counter(len(p) for p in payloads).most_common(6))
    bytes_table(payloads)


def everything() -> None:
    all_records = records()
    print(f"# заголовок записи, записей {len(all_records)}")
    bytes_table([r.raw[:probe.RECORD_HEADER] for _, r in all_records])
    for tag in sorted({r.tag for _, r in all_records}):
        layout(tag)


def pair(a: str, b: str) -> None:
    left, right = probe.walk(Path(a).read_bytes()), probe.walk(Path(b).read_bytes())
    print("записей", len(left), len(right))
    index = defaultdict(list)
    for r in right:
        index[r.tag, r.role, r.idx].append(r)
    for r in left:
        same = index[r.tag, r.role, r.idx]
        if not same:
            print("только слева", r.tag, hex(r.role), hex(r.idx), len(r.payload))
            continue
        other = same.pop(0)
        if other.raw != r.raw:
            size = min(len(r.raw), len(other.raw))
            spots = [i for i in range(size) if r.raw[i] != other.raw[i]]
            print(r.tag, hex(r.role), hex(r.idx), len(r.raw), len(other.raw), [hex(x) for x in spots[:16]])
    for rest in index.values():
        for r in rest:
            print("только справа", r.tag, hex(r.role), hex(r.idx), len(r.payload))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        census()
    elif args[0] == "--all":
        everything()
    elif args[0] == "--pair":
        pair(args[1], args[2])
    else:
        layout(args[0])


if __name__ == "__main__":
    main()
