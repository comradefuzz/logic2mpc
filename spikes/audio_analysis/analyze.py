#!/usr/bin/env python3
"""Анализ экспортированной дорожки для спайка 5. Только чтение, не код продукта.

Сетка берётся из проекта, звук из экспорта. Результат: сэмплы с границами,
срабатывания, остаток обратной сборки. Режим выбирается по данным:

    notes    у дорожки только ноты: проверка монофонии и выбор базовой ноты
    events   атак столько же, сколько регионов: каждый регион это один звук
    windows  иначе или есть Loop: повторы ищутся окнами по сетке тактов

    probe.py positions <project.logicx> --track NAME > grid.json
    analyze.py <track.wav> <grid.json> [--out analysis.json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import correlate

PPQ = 960
SILENCE = 10 ** (-60 / 20)
EVENT_RATIO = 1.2
EVENT_MATCH = 0.97
WINDOW_MATCH = 0.98
WINDOW_BARS = (1, 2, 4, 8, 16)
TAIL_SHARE = 1 / 8
ONSET_TOLERANCE = 0.02
PRE_ROLL = 0.02
COMPARE_LIMIT = 1.0
DECIMATE = 4
LEAD_IN = 2048


@dataclass(frozen=True)
class Position:
    tick: int
    loop_end: int | None = None


@dataclass(frozen=True)
class Note:
    tick: int
    pitch: int
    velocity: int
    length: int


@dataclass(frozen=True)
class Grid:
    positions: list[Position]
    bpm: float
    notes: list[Note] = field(default_factory=list)


@dataclass
class Sample:
    id: int
    start: int
    end: int
    hits: int = 0


@dataclass(frozen=True)
class Hit:
    sample: int
    position: int
    gain: float
    bar: float
    residual_db: float | None = None


@dataclass(frozen=True)
class Tail:
    start: int
    end: int


@dataclass(frozen=True)
class Base:
    pitch: int
    start: int
    end: int
    measured_pitch: float


@dataclass
class Analysis:
    mode: str
    samples: list[Sample] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    tails: list[Tail] = field(default_factory=list)
    onsets: int = 0
    missing: list[float] = field(default_factory=list)
    extra: list[float] = field(default_factory=list)
    spread_ms: float = 0.0
    residual_db: float | None = None
    window_bars: int | None = None
    polyphony: int | None = None
    base: Base | None = None


def ticks_to_samples(tick: int, bpm: float, sr: int) -> int:
    return round(tick * 60 / (PPQ * bpm) * sr)


def bar_of(position: int, bpm: float, sr: int) -> float:
    return position / (4 * 60 / bpm * sr) + 1


def find_onsets(mono: np.ndarray, sr: int, hop: int = 128) -> np.ndarray:
    """Атаки в отсчётах. Детектор даёт кадр, старт уточняется по огибающей."""
    # Запас тишины: иначе атака в самом начале файла не видна детектору.
    padded = np.r_[np.zeros(LEAD_IN), mono]
    envelope = librosa.onset.onset_strength(y=padded, sr=sr, hop_length=hop, n_fft=1024, aggregate=np.median)
    frames = librosa.onset.onset_detect(
        onset_envelope=envelope, sr=sr, hop_length=hop, units="frames", backtrack=False,
        pre_max=8, post_max=8, pre_avg=64, post_avg=64, delta=0.2, wait=int(0.03 * sr / hop),
    )
    points = librosa.frames_to_samples(frames, hop_length=hop, n_fft=1024) - LEAD_IN
    return np.array(sorted(refine_onset(mono, sr, max(0, int(p))) for p in points), dtype=int)


def refine_onset(mono: np.ndarray, sr: int, point: int) -> int:
    start = max(0, point - int(0.015 * sr))
    window = np.abs(mono[start : point + int(0.015 * sr)])
    if window.size == 0 or window.max() == 0:
        return point
    return start + int(np.argmax(window > 0.1 * window.max()))


def sound_end(mono: np.ndarray, start: int, limit: int) -> int:
    """Конец звука: последний отсчёт до `limit` выше порога тишины."""
    active = np.nonzero(np.abs(mono[start:limit]) > SILENCE)[0]
    return start + int(active[-1]) + 1 if active.size else start


def match(a: np.ndarray, b: np.ndarray, max_lag: int) -> tuple[float, int]:
    """Нормированная корреляция и сдвиг `a` относительно `b` в пределах `max_lag`."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0, 0
    full = correlate(a, b, mode="full", method="fft")
    centre = n - 1
    low = max(0, centre - max_lag)
    part = full[low : centre + max_lag + 1]
    index = int(np.argmax(np.abs(part)))
    return float(abs(part[index]) / norm), low + index - centre


def residual_db(audio: np.ndarray, rebuilt: np.ndarray) -> float | None:
    energy = float(np.sum(audio**2))
    if energy == 0:
        return None
    rest = float(np.sum((audio - rebuilt) ** 2))
    return 10 * float(np.log10(max(rest / energy, 1e-30)))


def compare_onsets(detected: np.ndarray, expected: list[int], sr: int, bpm: float) -> tuple[list[float], list[float]]:
    tolerance = ONSET_TOLERANCE * sr
    points = np.array(expected)
    missing = [
        round(bar_of(p, bpm, sr), 3)
        for p in expected
        if detected.size == 0 or np.abs(detected - p).min() > tolerance
    ]
    extra = [
        round(bar_of(int(p), bpm, sr), 3)
        for p in detected
        if points.size == 0 or np.abs(points - p).min() > tolerance
    ]
    return missing, extra


def analyze_events(audio: np.ndarray, mono: np.ndarray, sr: int, grid: Grid, onsets: np.ndarray) -> Analysis:
    starts = sorted({ticks_to_samples(p.tick, grid.bpm, sr) for p in grid.positions})
    limits = starts[1:] + [len(mono)]
    pre = int(PRE_ROLL * sr)
    compare = int(COMPARE_LIMIT * sr)
    ends = [sound_end(mono, s, limit) for s, limit in zip(starts, limits)]

    def piece(point: int, length: int) -> np.ndarray:
        begin = point - pre
        part = mono[max(0, begin) : point + length]
        return np.r_[np.zeros(max(0, -begin)), part]

    groups: list[list[int]] = []
    leaders: list[int] = []
    for index, (start, end) in enumerate(zip(starts, ends)):
        if end == start:
            continue
        for number, leader in enumerate(leaders):
            length = min(compare, end - start, ends[leader] - starts[leader])
            score, _ = match(piece(start, length), piece(starts[leader], length), pre)
            if score >= EVENT_MATCH:
                groups[number].append(index)
                break
        else:
            leaders.append(index)
            groups.append([index])

    result = Analysis("events", onsets=len(onsets))
    result.missing, result.extra = compare_onsets(onsets, starts, sr, grid.bpm)
    rebuilt = np.zeros_like(audio)
    lags: list[int] = []
    for number, members in enumerate(groups):
        # Образец это самый длинный звук с полным запасом перед атакой.
        clean = [i for i in members if starts[i] >= pre] or members
        leader = max(clean, key=lambda i: ends[i] - starts[i])
        begin = max(0, starts[leader] - pre)
        stereo = audio[begin : ends[leader]]
        reference = mono[begin : ends[leader]]
        lead = starts[leader] - begin
        hits = []
        for i in members:
            length = min(compare, ends[i] - starts[i], ends[leader] - starts[leader])
            _, lag = match(piece(starts[i], length), piece(starts[leader], length), pre)
            lags.append(lag)
            place = starts[i] + lag - lead
            skip = max(0, -place)
            place += skip
            stop = min(place + len(reference) - skip, limits[i])
            size = stop - place
            part = reference[skip : skip + size]
            energy = float(part @ part)
            gain = float(mono[place : stop] @ part) / energy if energy else 0.0
            rebuilt[place : stop] += gain * stereo[skip : skip + size]
            hits.append(Hit(number, starts[i] + lag, round(gain, 4), round(bar_of(starts[i] + lag, grid.bpm, sr), 3)))
        result.samples.append(Sample(number, begin, int(ends[leader]), len(hits)))
        result.hits.extend(hits)
    result.hits.sort(key=lambda h: h.position)
    if lags:
        centre = float(np.median(lags))
        result.spread_ms = round(max(abs(lag - centre) for lag in lags) / sr * 1000, 3)
    result.residual_db = residual_db(audio, rebuilt)
    return result


def active_span(mono: np.ndarray, start: int, stop: int) -> tuple[int, int] | None:
    window = mono[start:stop]
    if window.size == 0 or np.sqrt(np.mean(window**2)) <= SILENCE / 100:
        return None
    active = np.nonzero(np.abs(window) > SILENCE)[0]
    if active.size == 0:
        return None
    return start + int(active[0]), start + int(active[-1]) + 1


def same_window(a: np.ndarray, b: np.ndarray, bar: int) -> bool:
    """Окна равны, когда равен каждый такт: иначе короткий вариант теряется в длинном окне."""
    for start in range(0, len(a), bar):
        x, y = a[start : start + bar], b[start : start + bar]
        loud = np.max(np.abs(x)) > SILENCE, np.max(np.abs(y)) > SILENCE
        if loud[0] != loud[1]:
            return False
        if not loud[0]:
            continue
        if float(x @ y) / (float(np.linalg.norm(x) * np.linalg.norm(y)) or 1.0) < WINDOW_MATCH:
            return False
    return True


def group_windows(mono: np.ndarray, size: int, bar: int) -> tuple[list[int], list[int], list[Tail]]:
    """Окна по сетке тактов: номера окон по порядку и номера групп. Короткий остаток за окном это хвост."""
    reduced = mono[::DECIMATE]
    step = size // DECIMATE
    count = int(np.ceil(len(mono) / size))
    leaders: list[np.ndarray] = []
    windows: list[int] = []
    labels: list[int] = []
    tails: list[Tail] = []
    previous = False
    for index in range(count):
        span = active_span(mono, index * size, (index + 1) * size)
        if span is None:
            previous = False
            continue
        if previous and span[0] == index * size and span[1] - span[0] < size * TAIL_SHARE:
            tails.append(Tail(*span))
            previous = False
            continue
        previous = True
        part = reduced[index * step : (index + 1) * step]
        part = np.pad(part, (0, step - len(part)))
        for number, leader in enumerate(leaders):
            if same_window(part, leader, bar // DECIMATE):
                labels.append(number)
                break
        else:
            leaders.append(part)
            labels.append(len(leaders) - 1)
        windows.append(index)
    return windows, labels, tails


def analyze_windows(audio: np.ndarray, mono: np.ndarray, sr: int, grid: Grid, onsets: np.ndarray) -> Analysis:
    """Берётся окно с наименьшим числом разных кусков, при равенстве меньшее."""
    bar = round(4 * 60 / grid.bpm * sr)
    best = None
    for bars in WINDOW_BARS:
        found = group_windows(mono, bars * bar, bar)
        unique = len(set(found[1]))
        if unique and (best is None or unique < best[0]):
            best = (unique, bars, found)
    result = Analysis("windows", onsets=len(onsets))
    if best is None:
        return result
    _, bars, (windows, labels, tails) = best
    size = bars * bar
    result.window_bars = bars
    result.tails = tails
    rebuilt = np.zeros_like(audio)
    firsts: dict[int, int] = {}
    for window, label in zip(windows, labels):
        firsts.setdefault(label, window)
    counts = Counter(labels)
    for label, window in firsts.items():
        begin = window * size
        end = sound_end(mono, begin, min(begin + size, len(mono)))
        result.samples.append(Sample(label, begin, end, counts[label]))
    for window, label in zip(windows, labels):
        position = window * size
        sample = result.samples[label]
        stop = min(position + sample.end - sample.start, len(audio))
        length = stop - position
        part = mono[sample.start : sample.start + length]
        energy = float(part @ part)
        gain = float(mono[position:stop] @ part) / energy if energy else 0.0
        piece = gain * audio[sample.start : sample.start + length]
        rebuilt[position:stop] += piece
        rest = residual_db(audio[position:stop], piece)
        result.hits.append(
            Hit(label, position, round(gain, 4), round(bar_of(position, grid.bpm, sr), 3), None if rest is None else round(rest, 1))
        )
    for tail in tails:
        rebuilt[tail.start : tail.end] += audio[tail.start : tail.end]
    result.residual_db = residual_db(audio, rebuilt)
    return result


def polyphony(notes: list[Note]) -> int:
    events = sorted([(n.tick, 1) for n in notes] + [(n.tick + n.length, -1) for n in notes], key=lambda e: (e[0], e[1]))
    current = peak = 0
    for _, change in events:
        current += change
        peak = max(peak, current)
    return peak


def analyze_notes(mono: np.ndarray, sr: int, grid: Grid) -> Analysis:
    """Базовая нота-кандидат: самая длинная из самых частых, под которой есть звук."""
    result = Analysis("notes", polyphony=polyphony(grid.notes))
    frequent = Counter(n.pitch for n in grid.notes)
    for pitch, _ in frequent.most_common():
        for note in sorted((n for n in grid.notes if n.pitch == pitch), key=lambda n: -n.length):
            start = ticks_to_samples(note.tick, grid.bpm, sr)
            end = start + ticks_to_samples(note.length, grid.bpm, sr)
            part = mono[start:end]
            if part.size < 2048 or np.sqrt(np.mean(part**2)) <= SILENCE:
                continue
            pitches = librosa.yin(part, fmin=30, fmax=2000, sr=sr, frame_length=4096)
            measured = float(np.median(librosa.hz_to_midi(pitches)))
            result.base = Base(pitch, start, end, round(measured, 2))
            return result
    return result


def analyze(audio: np.ndarray, sr: int, grid: Grid) -> Analysis:
    mono = audio.mean(axis=1)
    if grid.notes and not grid.positions:
        return analyze_notes(mono, sr, grid)
    onsets = find_onsets(mono, sr)
    looped = any(p.loop_end is not None for p in grid.positions)
    events = len({p.tick for p in grid.positions})
    if not looped and events and events / EVENT_RATIO <= len(onsets) <= events * EVENT_RATIO:
        return analyze_events(audio, mono, sr, grid, onsets)
    return analyze_windows(audio, mono, sr, grid, onsets)


def load_grid(path: Path) -> Grid:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Grid(
        positions=[Position(p["tick"], p["loop_end"]) for p in data["positions"]],
        bpm=data["bpm"],
        notes=[Note(n["tick"], n["pitch"], n["velocity"], n["length"]) for n in data["notes"]],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wav", type=Path)
    parser.add_argument("grid", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    audio, sr = sf.read(args.wav, always_2d=True)
    result = analyze(audio, sr, load_grid(args.grid))
    text = json.dumps(asdict(result), ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
