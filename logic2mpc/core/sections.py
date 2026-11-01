"""Секции песни по маркерам, правило AN-063."""
from __future__ import annotations

from dataclasses import dataclass

from .model import BAR


@dataclass(frozen=True)
class Section:
    name: str
    start: int
    bars: int

    @property
    def end(self) -> int:
        return self.start + self.bars * BAR


def sections_from_markers(markers: list[tuple[int, str | None]], song_end: int) -> list[Section]:
    points = sorted(markers)
    if not points or points[0][0] > 0:
        points = [(0, None), *points]
    starts = [tick for tick, _ in points]
    stops = starts[1:] + [max(song_end, starts[-1] + 1)]
    sections = []
    for number, ((start, name), stop) in enumerate(zip(points, stops), 1):
        bars = -((start - stop) // BAR)
        sections.append(Section(name or f"Section {number:02d}", start, bars))
    return sections


def section_at(tick: int, sections: list[Section]) -> int:
    return max((i for i, s in enumerate(sections) if s.start <= tick), default=0)


def place(tick: int, sections: list[Section]) -> tuple[int, int]:
    """Номер секции и время от её начала."""
    index = section_at(tick, sections)
    return index, tick - sections[index].start


def crossings(ticks: list[int], length: int, sections: list[Section]) -> list[int]:
    """Вхождения, которые звучат за концом своей секции."""
    return [t for t in ticks if t + length > sections[section_at(t, sections)].end]
