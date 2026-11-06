#!/usr/bin/env python3
"""Решение по дорожке и нарезка для ревью, спайк S-009. Не код продукта.

Фрагменты дорожки сравниваются один раз и складываются в дерево сходства. Решительность
выбирает уровень его разреза: 0 сохраняет каждое отличие, 1 оставляет один фрагмент.

    probe.py positions <project.logicx> --track NAME > grid.json
    decide.py <track.wav> <grid.json> --code ELA --group SY --name Saw --out DIR
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.signal import resample_poly
from scipy.spatial.distance import squareform

import analyze

WINDOW_BARS = (1, 2, 4, 8)
MAX_VARIANTS = 4
DEFAULT = 0.775
REDUCE = 4
FRAME = 0.05
FLOOR_DB = -60.0
CEILING_DB = 20.0
CLEAN_DB = -40.0
FADE_IN = 0.002
FADE_OUT = 0.01
EDGE = 4


@dataclass(frozen=True)
class Member:
    position: int
    bar: float
    difference_db: float
    worst_bar: float | None
    lost_tail: int


@dataclass(frozen=True)
class Group:
    start: int
    end: int
    bar: float
    confidence: float
    members: list[Member]


@dataclass(frozen=True)
class Decision:
    decisiveness: float
    verdict: str
    window_bars: int
    confidence: float
    coverage: float
    uncovered: list[float]
    groups: list[Group]


@dataclass(frozen=True)
class Layout:
    bars: int
    positions: list[int]
    distances: np.ndarray
    worst: np.ndarray
    ends: list[int]
    tree: np.ndarray | None


@dataclass(frozen=True)
class Measured:
    layouts: list[Layout]
    sr: int
    bar: int


def threshold(value: float) -> float:
    return FLOOR_DB + value * (CEILING_DB - FLOOR_DB)


def confidence_of(db: float) -> float:
    """Единица минус решительность, при которой такое различие сливается порогом."""
    return round(1 - (min(max(db, FLOOR_DB), CEILING_DB) - FLOOR_DB) / (CEILING_DB - FLOOR_DB), 3)


def difference(a: np.ndarray, b: np.ndarray, frame: int) -> tuple[float, int]:
    """Худший кадр разницы к средней энергии кадра, дБ, и начало кадра. Без корреляции места нет: −1."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    energy = float(b @ b)
    gain = float(a @ b) / energy if energy else 0.0
    if gain <= 0:
        return CEILING_DB, -1
    rest = a - gain * b
    count = int(np.ceil(n / frame))
    frames = np.sum(np.pad(rest, (0, count * frame - n)).reshape(count, frame) ** 2, axis=1)
    reference = max(float(a @ a), gain**2 * energy) / count
    index = int(np.argmax(frames))
    db = 10 * np.log10(max(float(frames[index]) / reference, 1e-30))
    return min(max(float(db), FLOOR_DB), CEILING_DB), index * frame


def first_position(grid: analyze.Grid, sr: int) -> int:
    ticks = [p.tick for p in grid.positions] + [n.tick for n in grid.notes]
    return analyze.ticks_to_samples(min(ticks), grid.bpm, sr) if ticks else 0


def reduce_piece(mono: np.ndarray, start: int, size: int) -> np.ndarray:
    """Каждый фрагмент прореживается сам по себе: фильтр не тянет в него соседний звук."""
    piece = mono[start : start + size]
    return resample_poly(np.pad(piece, (0, size - len(piece))), 1, REDUCE)


def first_sound(mono: np.ndarray, first: int, bar: int) -> int:
    """Первый такт от начала региона, где есть звук: сетка тактов сохраняется."""
    active = np.nonzero(np.abs(mono[first:]) > analyze.SILENCE)[0]
    return first + int(active[0]) // bar * bar if active.size else first


def layout(mono: np.ndarray, sr: int, first: int, bars: int, bar: int) -> Layout:
    size = bars * bar
    positions: list[int] = []
    ends: list[int] = []
    previous = False
    for start in range(first, len(mono), size):
        span = analyze.active_span(mono, start, start + size)
        if span is None:
            previous = False
        elif previous and span[0] == start and span[1] - span[0] < size * analyze.TAIL_SHARE:
            # Хвост это не фрагмент, он остаётся в конце предыдущего.
            ends[-1] = span[1]
            previous = False
        else:
            positions.append(start)
            ends.append(span[1])
            previous = True
    frame = int(FRAME * sr) // REDUCE
    parts = [reduce_piece(mono, p, size) for p in positions]
    count = len(parts)
    distances = np.zeros((count, count))
    worst = np.zeros((count, count), dtype=int)
    for i in range(count):
        for j in range(i + 1, count):
            distances[i, j], worst[i, j] = difference(parts[i], parts[j], frame)
            distances[j, i], worst[j, i] = distances[i, j], worst[i, j]
    return Layout(bars, positions, distances, worst * REDUCE, ends, tree_of(distances))


def measure(audio: np.ndarray, sr: int, grid: analyze.Grid) -> Measured:
    mono = audio.mean(axis=1)
    bar = round(4 * 60 / grid.bpm * sr)
    first = first_sound(mono, first_position(grid, sr), bar)
    return Measured([layout(mono, sr, first, bars, bar) for bars in WINDOW_BARS], sr, bar)


def tree_of(distances: np.ndarray) -> np.ndarray | None:
    if len(distances) < 2:
        return None
    # Дерево принимает только неотрицательные расстояния, поэтому шкала сдвинута к нулю.
    shifted = distances - FLOOR_DB
    np.fill_diagonal(shifted, 0)
    return linkage(squareform(shifted, checks=False), method="complete")


def labels_of(item: Layout, value: float) -> np.ndarray:
    if item.tree is None:
        return np.ones(len(item.positions), dtype=int)
    return fcluster(item.tree, threshold(value) - FLOOR_DB + 1e-9, criterion="distance")


def group_of(item: Layout, indices: list[int], measured: Measured) -> Group:
    # Образец это фрагмент, ближайший к остальным.
    leader = min(indices, key=lambda i: float(item.distances[i, indices].sum()))
    length = item.ends[leader] - item.positions[leader]
    members = []
    for i in indices:
        db = FLOOR_DB if i == leader else float(item.distances[i, leader])
        offset = int(item.worst[i, leader])
        point = None if offset < 0 else bar_at(item.positions[i] + offset, measured)
        lost = max(0, item.ends[i] - item.positions[i] - length)
        members.append(Member(item.positions[i], bar_at(item.positions[i], measured), round(db, 1), point, lost))
    # Полная связь сливает группу по самой дальней паре.
    widest = max((float(item.distances[i, j]) for i in indices for j in indices if i != j), default=FLOOR_DB)
    return Group(item.positions[leader], item.ends[leader], bar_at(item.positions[leader], measured), confidence_of(widest), members)


def bar_at(position: int, measured: Measured) -> float:
    return round(position / measured.bar + 1, 3)


def cut(measured: Measured, value: float) -> Decision:
    """Длина фрагмента выбирается при значении по умолчанию: решительность не меняет деление дорожки.

    Берутся деления, где фрагментов не больше лимита. Из них выигрывает наименьшая сумма тактов,
    при равенстве меньшее число фрагментов. Если таких делений нет, дорожка не режется чисто
    и берётся самая длинная длина: от значения по умолчанию вправо такая дорожка
    сливается в один фрагмент принудительно, влево режется порогом как обычно.
    """
    filled = [item for item in measured.layouts if item.positions]
    if not filled:
        return Decision(value, "uncut", WINDOW_BARS[0], 0.0, 0.0, [], [])

    def cost(item: Layout) -> tuple[int, int]:
        count = len(set(labels_of(item, DEFAULT)))
        return count * item.bars, count

    fitting = [item for item in filled if cost(item)[1] <= MAX_VARIANTS]
    uncut = not fitting
    item = filled[-1] if uncut else min(fitting, key=cost)
    labels = np.ones(len(item.positions), dtype=int) if uncut and value >= DEFAULT else labels_of(item, value)
    indices = [[int(i) for i in np.nonzero(labels == label)[0]] for label in sorted(set(labels))]
    indices.sort(key=lambda found: (-len(found), found[0]))
    groups = [group_of(item, found, measured) for found in indices]
    members = [m for g in groups for m in g.members]
    uncovered = sorted(m.bar for m in members if m.difference_db > CLEAN_DB or m.lost_tail)
    coverage = 1 - len(uncovered) / len(members)
    confidence = min(g.confidence for g in groups)
    verdict = "uncut" if uncut else "lossy" if uncovered else "clean"
    return Decision(value, verdict, item.bars, confidence, round(coverage, 3), uncovered, groups)


def faded(piece: np.ndarray, sr: int) -> np.ndarray:
    """Край, где звук обрывается, получает короткий спад: иначе на нём щелчок."""
    out = piece.copy()
    for size, edge in ((int(FADE_IN * sr), slice(None, None)), (int(FADE_OUT * sr), slice(None, None, -1))):
        size = min(size, len(out))
        view = out[edge][:size]
        # Оборван только край, где звук есть уже в крайних отсчётах: атака от нуля не трогается.
        if np.max(np.abs(out[edge][:EDGE])) > analyze.SILENCE:
            view *= np.sin(np.linspace(0, np.pi / 2, size))[:, None]
    return out


def report(decision: Decision, name: str, version: int, refusal: str | None) -> str:
    lines = [
        f"# {name}, версия {version}",
        "",
        f"Вердикт: {decision.verdict}. Решительность {decision.decisiveness}, уверенность {decision.confidence}.",
        f"Длина фрагмента {decision.window_bars} тактов, фрагментов {len(decision.groups)}, покрыто точно {decision.coverage:.0%} вхождений.",
    ]
    if decision.uncovered:
        lines.append("Не покрыты точно такты: " + ", ".join(map(str, decision.uncovered)) + ".")
    if refusal:
        lines += ["", f"Причина пересмотра: {refusal}"]
    for number, group in enumerate(decision.groups, 1):
        lines += ["", f"## Фрагмент {number:02d}", "", f"Взят с такта {group.bar}, вхождений {len(group.members)}, уверенность {group.confidence}.", ""]
        replaced = [m for m in group.members if m.difference_db > CLEAN_DB or m.lost_tail]
        for member in replaced:
            if member.difference_db > CLEAN_DB:
                place = "похожего нет" if member.worst_bar is None else f"сильнее всего на такте {member.worst_bar}"
                lines.append(f"- Такт {member.bar}: заменён, различие {member.difference_db} дБ, {place}")
            if member.lost_tail:
                lines.append(f"- Такт {member.bar}: потерян хвост {member.lost_tail} отсчётов")
        if not replaced:
            lines.append("- Все вхождения совпали")
    return "\n".join(lines) + "\n"


def write_version(
    out: Path, audio: np.ndarray, sr: int, decision: Decision, code: str, group: str, name: str, refusal: str | None = None
) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    version = 1 + sum(1 for p in out.glob("v*") if p.is_dir())
    folder = out / f"v{version}"
    folder.mkdir()
    for number, piece in enumerate(decision.groups, 1):
        sf.write(folder / f"{code}_{group}_{name}_{number:02d}.wav", faded(audio[piece.start : piece.end], sr), sr, subtype="PCM_24")
    data = dict(version=version, refusal=refusal, **asdict(decision))
    (folder / "decision.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "report.md").write_text(report(decision, name, version, refusal), encoding="utf-8")
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wav", type=Path)
    parser.add_argument("grid", type=Path)
    parser.add_argument("--decisiveness", type=float, default=DEFAULT)
    parser.add_argument("--code", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--refusal")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audio, sr = sf.read(args.wav, always_2d=True)
    measured = measure(audio, sr, analyze.load_grid(args.grid))
    decision = cut(measured, args.decisiveness)
    print(write_version(args.out, audio, sr, decision, args.code, args.group, args.name, args.refusal))


if __name__ == "__main__":
    main()
