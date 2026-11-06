"""Типы ядра: что известно о дорожке и что решил анализ."""
from __future__ import annotations

from dataclasses import dataclass, field

PPQ = 960
BAR = PPQ * 4


@dataclass(frozen=True)
class Note:
    tick: int
    pitch: int
    velocity: int
    length: int


@dataclass(frozen=True)
class MidiRegion:
    """Ноты с временем от начала региона."""

    tick: int
    notes: list[Note]
    muted: bool = False


@dataclass(frozen=True)
class AudioRegion:
    tick: int
    loop_end: int | None = None
    length: int | None = None
    muted: bool = False
    source: int | None = None
    offset: int | None = None
    frames: int | None = None


@dataclass(frozen=True)
class Track:
    row: int
    name: str
    group: str | None
    midi_regions: list[MidiRegion]
    audio_regions: list[AudioRegion]


@dataclass(frozen=True)
class Occurrence:
    """`length` задан у недоигранного прохода: нота короче фрагмента."""

    tick: int
    gain: float = 1.0
    length: int | None = None


@dataclass
class Piece:
    """Фрагмент дорожки: границы в кадрах экспорта. `lead` запас перед атакой, в кадрах.

    Позиция вхождения это атака: по ней выбирается секция, нота ставится раньше на запас образца.
    """

    start: int
    end: int
    confidence: float
    occurrences: list[Occurrence]
    lead: int = 0
    start_open: bool = False
    end_open: bool = False


@dataclass
class Cut:
    rule: str
    confidence: float
    pieces: list[Piece]
    cycle_bars: int | None = None
    lost_bars: list[float] = field(default_factory=list)
    muted_bars: list[float] = field(default_factory=list)
    replaced_bars: list[float] = field(default_factory=list)
    remark: str | None = None
