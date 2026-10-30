#!/usr/bin/env python3
"""Сверяет файлы Export All Tracks со строками probe.py. Только чтение, не код продукта.

    match.py <project.logicx> <папка с файлами> [--threshold 0.001]
"""
from __future__ import annotations

import argparse
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "logic_read"))
import probe  # noqa: E402

NAME = re.compile(r"^(\d+)_(.*)\.wav$", re.IGNORECASE)


def sounding_range(path: Path, threshold: float) -> tuple[int, int, int, int, int] | None:
    """Первый и последний кадр со звуком, всего кадров, частота, каналы. Нужен 24-бит PCM."""
    with wave.open(str(path)) as audio:
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        rate = audio.getframerate()
        frames = audio.getnframes()
        data = audio.readframes(frames)
    if width != 3:
        raise ValueError(f"{path.name}: ожидалось 24 бита, получено {width * 8}")
    limit = threshold * 2**23
    first = last = None
    for frame in range(frames):
        for channel in range(channels):
            offset = (frame * channels + channel) * width
            value = int.from_bytes(data[offset : offset + width], "little", signed=True)
            if abs(value) > limit:
                first = frame if first is None else first
                last = frame
                break
    return None if first is None else (first, last, frames, rate, channels)


def seconds_at(tick: int, tempo: list[tuple[int, float]]) -> float:
    total = 0.0
    points = sorted(tempo)
    for number, (start, bpm) in enumerate(points):
        end = points[number + 1][0] if number + 1 < len(points) else tick
        if tick <= start:
            break
        total += (min(tick, end) - start) / probe.PPQ * 60 / bpm
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--threshold", type=float, default=0.001)
    args = parser.parse_args()

    records = probe.walk(probe.load(args.project, None)[1])
    rows = probe.arrange_rows(records)
    tempo = probe.tempo_map(records)
    regions = probe.regions(records)
    files = {}
    for path in sorted(args.folder.iterdir()):
        match = NAME.match(path.name)
        if not match:
            print(f"файл не по шаблону: {path.name}")
            continue
        number = int(match.group(1)) - 1
        if number in files:
            print(f"номер занят: {path.name} и {files[number][0].name}")
            continue
        files[number] = (path, match.group(2))

    for number, (kind, _, name) in enumerate(rows):
        own = [r for r in regions if r.row == number]
        expected = min((seconds_at(r.tick, tempo) for r in own), default=None)
        if number not in files:
            print(f"{number + 1:02d} {name}: файла нет, регионов {len(own)}, тип строки {kind}")
            continue
        path, file_name = files.pop(number)
        note = "" if file_name == name else f" (имя в файле: {file_name})"
        span = sounding_range(path, args.threshold)
        if span is None:
            print(f"{number + 1:02d} {name}{note}: тишина, регионов {len(own)}")
            continue
        first, last, frames, rate, channels = span
        line = (
            f"{number + 1:02d} {name}{note}: звук {first / rate:.3f}–{last / rate:.3f} с, "
            f"файл {frames / rate:.3f} с, {rate} Гц, 24 бита, каналов {channels}"
        )
        if expected is not None:
            line += f", ожидался старт {expected:.3f} с, разница {first / rate - expected:+.3f}"
        print(line)
    for number, (path, _) in sorted(files.items()):
        print(f"файл без строки: {path.name}")


if __name__ == "__main__":
    main()
