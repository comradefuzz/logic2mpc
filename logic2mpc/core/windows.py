"""Деление дорожки окнами и сравнением звука, правило AN-013. Перенесено из spikes/audio_analysis/decide.py."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.signal import resample_poly
from scipy.spatial.distance import squareform

from .signal import SILENCE

WINDOW_BARS = (1, 2, 4, 8)
MAX_VARIANTS = 4
DEFAULT = 0.775
REDUCE = 4
FRAME = 0.05
FLOOR_DB = -60.0
CEILING_DB = 20.0
CLEAN_DB = -40.0
TAIL_SHARE = 1 / 8


@dataclass(frozen=True)
class Member:
    position: int
    difference_db: float
    lost_tail: int


@dataclass(frozen=True)
class Group:
    start: int
    end: int
    confidence: float
    members: list[Member]


@dataclass(frozen=True)
class Decision:
    verdict: str
    bars: int
    confidence: float
    uncovered: list[int]
    groups: list[Group]


@dataclass(frozen=True)
class Layout:
    bars: int
    positions: list[int]
    distances: np.ndarray
    ends: list[int]
    tree: np.ndarray | None


def threshold(value: float) -> float:
    return FLOOR_DB + value * (CEILING_DB - FLOOR_DB)


def confidence_of(db: float) -> float:
    """Единица минус решительность, при которой такое различие сливается порогом."""
    return round(1 - (min(max(db, FLOOR_DB), CEILING_DB) - FLOOR_DB) / (CEILING_DB - FLOOR_DB), 3)


def difference(a: np.ndarray, b: np.ndarray, frame: int) -> float:
    """Худший кадр разницы к средней энергии кадра, дБ."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    energy = float(b @ b)
    gain = float(a @ b) / energy if energy else 0.0
    if gain <= 0:
        return CEILING_DB
    rest = a - gain * b
    count = int(np.ceil(n / frame))
    frames = np.sum(np.pad(rest, (0, count * frame - n)).reshape(count, frame) ** 2, axis=1)
    reference = max(float(a @ a), gain**2 * energy) / count
    db = 10 * np.log10(max(float(frames.max()) / reference, 1e-30))
    return min(max(float(db), FLOOR_DB), CEILING_DB)


def reduce_piece(mono: np.ndarray, start: int, size: int) -> np.ndarray:
    """Каждый кусок прореживается сам по себе: фильтр не тянет в него соседний звук."""
    piece = mono[start : start + size]
    return resample_poly(np.pad(piece, (0, size - len(piece))), 1, REDUCE)


def active_span(mono: np.ndarray, start: int, stop: int) -> tuple[int, int] | None:
    window = mono[start:stop]
    if window.size == 0 or np.sqrt(np.mean(window**2)) <= SILENCE / 100:
        return None
    active = np.nonzero(np.abs(window) > SILENCE)[0]
    if active.size == 0:
        return None
    return start + int(active[0]), start + int(active[-1]) + 1


def first_sound(mono: np.ndarray, first: int, bar: int) -> int:
    """Первый такт от начала региона, где есть звук: сетка тактов сохраняется."""
    active = np.nonzero(np.abs(mono[first:]) > SILENCE)[0]
    return first + int(active[0]) // bar * bar if active.size else first


def layout(mono: np.ndarray, sr: int, first: int, bars: int, bar: int) -> Layout:
    size = bars * bar
    positions: list[int] = []
    ends: list[int] = []
    previous = False
    for start in range(first, len(mono), size):
        span = active_span(mono, start, start + size)
        if span is None:
            previous = False
        elif previous and span[0] == start and span[1] - span[0] < size * TAIL_SHARE:
            # Хвост это не кусок, он остаётся в конце предыдущего.
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
    for i in range(count):
        for j in range(i + 1, count):
            distances[i, j] = distances[j, i] = difference(parts[i], parts[j], frame)
    return Layout(bars, positions, distances, ends, tree_of(distances))


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


def group_of(item: Layout, indices: list[int]) -> Group:
    # Образец это кусок, ближайший к остальным.
    leader = min(indices, key=lambda i: float(item.distances[i, indices].sum()))
    length = item.ends[leader] - item.positions[leader]
    members = []
    for i in indices:
        db = FLOOR_DB if i == leader else float(item.distances[i, leader])
        lost = max(0, item.ends[i] - item.positions[i] - length)
        members.append(Member(item.positions[i], round(db, 1), lost))
    # Полная связь сливает группу по самой дальней паре.
    widest = max((float(item.distances[i, j]) for i in indices for j in indices if i != j), default=FLOOR_DB)
    return Group(item.positions[leader], item.ends[leader], confidence_of(widest), members)


def cut(mono: np.ndarray, sr: int, first: int, bar: int, value: float = DEFAULT) -> Decision:
    """Берутся деления, где кусков не больше лимита, из них наименьшая сумма тактов, затем меньшее число кусков.

    Если таких делений нет, дорожка не режется чисто: берётся самая длинная длина, и от значения
    по умолчанию вправо такая дорожка сливается в один кусок принудительно.
    """
    start = first_sound(mono, first, bar)
    layouts = [layout(mono, sr, start, bars, bar) for bars in WINDOW_BARS]
    filled = [item for item in layouts if item.positions]
    if not filled:
        return Decision("uncut", WINDOW_BARS[0], 0.0, [], [])

    def cost(item: Layout) -> tuple[int, int]:
        count = len(set(labels_of(item, DEFAULT)))
        return count * item.bars, count

    fitting = [item for item in filled if cost(item)[1] <= MAX_VARIANTS]
    uncut = not fitting
    item = filled[-1] if uncut else min(fitting, key=cost)
    labels = np.ones(len(item.positions), dtype=int) if uncut and value >= DEFAULT else labels_of(item, value)
    indices = [[int(i) for i in np.nonzero(labels == label)[0]] for label in sorted(set(labels))]
    indices.sort(key=lambda found: (-len(found), found[0]))
    groups = [group_of(item, found) for found in indices]
    members = [m for g in groups for m in g.members]
    uncovered = sorted(m.position for m in members if m.difference_db > CLEAN_DB or m.lost_tail)
    verdict = "uncut" if uncut else "lossy" if uncovered else "clean"
    return Decision(verdict, item.bars, min(g.confidence for g in groups), uncovered, groups)
