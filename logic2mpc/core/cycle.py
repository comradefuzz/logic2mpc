"""Цикл MIDI-партии по нотам: правила AN-021, AN-022, AN-023, AN-030 из docs/analysis.md."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .model import BAR, MidiRegion

LENGTHS = (1, 2, 4, 8)
SNAP = 60  # 1/64
CORE_SHARE = 0.5
PASS_SHARE = 0.7
BEST_SHARE = 0.9
REGION_MATCH = 0.7
REGION_SHARE = 0.5

Point = tuple[int, int]


@dataclass(frozen=True)
class Cycle:
    bars: int
    start: int
    passes: list[int]
    core: frozenset[Point]
    score: float
    source: str


def absolute(regions: list[MidiRegion]) -> list[tuple[int, int, int]]:
    return sorted({(r.tick + n.tick, n.pitch, n.length) for r in regions for n in r.notes})


def region_type(region: MidiRegion) -> frozenset[Point]:
    return frozenset((round(n.tick / SNAP), n.pitch) for n in region.notes)


def similarity(a: frozenset[Point], b: frozenset[Point]) -> float:
    return 2 * len(a & b) / (len(a) + len(b)) if a or b else 1.0


def windows(notes: list[tuple[int, int, int]], size: int, start: int) -> dict[int, set[Point]]:
    """Проходы от `start`: начало прохода и точки «время внутри прохода, высота»."""
    found: dict[int, set[Point]] = {}
    for tick, pitch, _ in notes:
        if tick < start:
            continue
        offset = (tick - start) % size
        found.setdefault(tick - offset, set()).add((round(offset / SNAP), pitch))
    return found


def fit(notes: list[tuple[int, int, int]], bars: int, start: int, source: str) -> Cycle | None:
    size = bars * BAR
    origin = start % size
    # Сетка идёт через всю партию: проходы раньше начала тоже входят в цикл, AN-020a.
    found = windows(notes, size, origin - size if notes[0][0] < origin else origin)
    if not found:
        return None
    counts = Counter(point for points in found.values() for point in points)
    core = frozenset(p for p, n in counts.items() if n >= len(found) * CORE_SHARE)
    if not core:
        return None
    passes = sorted(t for t, points in found.items() if len(points & core) / len(core) >= PASS_SHARE)
    explained = sum(counts[p] for p in core) / sum(counts.values())
    return Cycle(bars, passes[0] if passes else start, passes, core, explained * len(passes) / len(found), source)


def period(regions: list[MidiRegion]) -> int | None:
    """Период последовательности типов регионов, в тактах. AN-021."""
    filled = [r for r in regions if r.notes]
    types = {r.tick: region_type(r) for r in filled}
    if len(set(types.values())) == len(types):
        return None
    for bars in LENGTHS:
        step = bars * BAR
        pairs = [(t, t + step) for t in types if t + step in types]
        equal = [(a, b) for a, b in pairs if types[a] == types[b]]
        linked = {t for pair in equal for t in pair}
        if pairs and len(equal) / len(pairs) >= REGION_MATCH and len(linked) / len(types) >= REGION_SHARE:
            return bars
    return None


def phase(regions: list[MidiRegion], bars: int) -> int:
    """Начало цикла: сетка цикла от начала песни, если там есть регион, иначе первый повторяющийся регион."""
    step = bars * BAR
    types = {r.tick: region_type(r) for r in regions if r.notes}
    repeated = sorted(t for t in types if types.get(t + step) == types[t])
    on_grid = [t for t in repeated if t % step == 0]
    if on_grid:
        return on_grid[0]
    # Регион мог быть вторым в проходе: проход тогда начинается на сетке раньше него.
    for tick in repeated:
        grid = tick - tick % step
        if grid in types:
            return grid
    return repeated[0]


def find_cycle(regions: list[MidiRegion]) -> Cycle | None:
    audible = [r for r in regions if not r.muted]
    notes = absolute(audible)
    if not notes:
        return None
    bars = period(audible)
    if bars is not None:
        cycle = fit(notes, bars, phase(audible, bars), "AN-021")
        if cycle:
            return cycle
    first = notes[0][0] // BAR * BAR
    best: dict[int, Cycle] = {}
    for bars in LENGTHS:
        found = [fit(notes, bars, first + shift * BAR, "AN-022") for shift in range(bars)]
        found = [c for c in found if c and len(windows(notes, bars * BAR, first)) > 1]
        if found:
            best[bars] = max(found, key=lambda c: c.score)
    if not best:
        return None
    top = max(c.score for c in best.values())
    return best[min(b for b, c in best.items() if c.score >= BEST_SHARE * top)]


def pass_notes(notes: list[tuple[int, int, int]], start: int, size: int) -> frozenset[tuple[int, int, int]]:
    return frozenset((t - start, p, n) for t, p, n in notes if start <= t < start + size)


def common_pass(notes: list[tuple[int, int, int]], passes: list[int], size: int) -> int:
    """Самый частый точный вариант прохода. Из него проход, за которым тот же вариант идёт следом. AN-030."""
    variants = {start: pass_notes(notes, start, size) for start in passes}
    counts = Counter(variants.values())
    top = max(counts.values())
    best = [start for start, variant in variants.items() if counts[variant] == top]
    best = [start for start in best if counts[variants[start]] == counts[variants[best[0]]] and variants[start] == variants[best[0]]]
    return next((start for start in best if variants.get(start + size) == variants[start]), best[0])
