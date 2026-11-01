"""Анализ дорожки на синтетике с известной структурой."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

SR = 48000
BEAT_TICKS = 960
BAR_TICKS = 3840
BAR = 96000
GRID = dict(bpm=120.0, notes=[])


def hit(freq: float, length: int = 11000, seed: int = 1) -> np.ndarray:
    t = np.arange(length) / SR
    noise = np.random.default_rng(seed).normal(0, 0.3, length)
    return (np.sin(2 * np.pi * freq * t) + noise) * np.exp(-t * 30) * 0.5


def stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono * 0.9], axis=1)


def place(length: int, events: list[tuple[int, np.ndarray]]) -> np.ndarray:
    out = np.zeros(length)
    for start, sound in events:
        end = min(start + len(sound), length)
        out[start:end] += sound[: end - start]
    return stereo(out)


def beats(count: int) -> list[int]:
    return [i * BEAT_TICKS for i in range(count)]


def positions(ticks: list[int]) -> list[analyze.Position]:
    return [analyze.Position(t) for t in ticks]


def pattern(bars: int, seed: int = 2) -> np.ndarray:
    """Плотный рисунок: удар на каждую шестнадцатую, все удары разные."""
    out = np.zeros(bars * BAR)
    rng = np.random.default_rng(seed)
    for step in range(bars * 16):
        sound = hit(float(rng.uniform(300, 3000)), 3000, seed + step)
        out[step * 6000 : step * 6000 + 3000] += sound
    return out


def test_one_shot() -> None:
    ticks = beats(32)
    audio = place(17 * BAR, [(t * 25, hit(80)) for t in ticks])
    result = analyze.analyze(audio, SR, analyze.Grid(positions=positions(ticks), **GRID))
    assert result.mode == "events"
    assert len(result.samples) == 1
    assert len(result.hits) == 32
    assert result.missing == [] and result.extra == []
    assert result.spread_ms <= 1
    assert result.residual_db < -60


def test_shifted_hits_are_aligned() -> None:
    ticks = beats(16)
    shifts = np.random.default_rng(6).integers(-200, 200, 16)
    audio = place(9 * BAR, [(t * 25 + 240 + int(s), hit(80)) for t, s in zip(ticks, shifts)])
    result = analyze.analyze(audio, SR, analyze.Grid(positions=positions(ticks), **GRID))
    assert len(result.samples) == 1
    expected = np.array([t * 25 + 240 + int(s) for t, s in zip(ticks, shifts)])
    found = np.array([h.position for h in result.hits])
    assert np.ptp(found - expected) == 0
    assert result.residual_db < -40


def test_one_shot_with_gains() -> None:
    ticks = beats(16)
    gains = np.random.default_rng(3).uniform(0.5, 1.0, 16)
    audio = place(9 * BAR, [(t * 25, g * hit(80)) for t, g in zip(ticks, gains)])
    result = analyze.analyze(audio, SR, analyze.Grid(positions=positions(ticks), **GRID))
    assert len(result.samples) == 1
    found = np.array([h.gain for h in result.hits])
    ratio = found / gains
    assert np.allclose(ratio, ratio[0], atol=0.02)
    assert result.residual_db < -40


def test_two_sounds_stay_apart() -> None:
    ticks = beats(16)
    sounds = [hit(80, seed=1), hit(2500, seed=5)]
    audio = place(9 * BAR, [(t * 25, sounds[i % 2]) for i, t in enumerate(ticks)])
    result = analyze.analyze(audio, SR, analyze.Grid(positions=positions(ticks), **GRID))
    assert len(result.samples) == 2
    assert sorted(s.hits for s in result.samples) == [8, 8]


def test_loop_stays_whole() -> None:
    bar = pattern(2)
    audio = place(16 * BAR, [(i * 2 * BAR, bar) for i in range(8)])
    grid = analyze.Grid(positions=[analyze.Position(0, 16 * BAR_TICKS)], **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert result.mode == "windows"
    assert result.window_bars == 2
    assert len(result.samples) == 1
    assert len(result.hits) == 8
    assert result.residual_db < -60


def test_loop_gains_are_fitted() -> None:
    bar = pattern(2)
    gains = [1.0, 0.5] * 4
    audio = place(16 * BAR, [(i * 2 * BAR, g * bar) for i, g in enumerate(gains)])
    grid = analyze.Grid(positions=[analyze.Position(0, 16 * BAR_TICKS)], **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert len(result.samples) == 1
    assert np.allclose([h.gain for h in result.hits], gains, atol=0.01)
    assert result.residual_db < -60
    assert all(h.residual_db < -60 for h in result.hits)


def test_window_residual_shows_merged_difference() -> None:
    phrase = pattern(2)
    changed = phrase.copy()
    changed[:1200] *= 0.2
    audio = place(8 * BAR, [(0, phrase), (2 * BAR, changed), (4 * BAR, phrase), (6 * BAR, phrase)])
    grid = analyze.Grid(positions=[analyze.Position(0, 8 * BAR_TICKS)], **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert len(result.samples) == 1
    worst = max(result.hits, key=lambda h: h.residual_db)
    assert worst.position == 2 * BAR
    assert worst.residual_db > -60


def test_inverted_window_is_not_the_same() -> None:
    bar = pattern(2)
    audio = place(8 * BAR, [(0, bar), (2 * BAR, -bar), (4 * BAR, bar), (6 * BAR, -bar)])
    grid = analyze.Grid(positions=[analyze.Position(0, 8 * BAR_TICKS)], **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert len(result.samples) != 1 or all(h.gain > 0 for h in result.hits)


def test_short_variant_stays_apart() -> None:
    phrase = pattern(8)
    short = phrase.copy()
    short[int(7.5 * BAR) :] = 0
    events = [(0, phrase), (8 * BAR, phrase), (16 * BAR, short), (24 * BAR, phrase)]
    audio = place(32 * BAR, events)
    grid = analyze.Grid(positions=positions([i * 8 * BAR_TICKS for i in range(4)]), **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert result.window_bars == 8
    assert sorted(s.hits for s in result.samples) == [1, 3]


def test_sustained_phrase_with_few_onsets_is_not_events() -> None:
    t = np.arange(4 * BAR) / SR
    pad = 0.3 * np.sin(2 * np.pi * 220 * t)
    ticks = [i * 4 * BAR_TICKS for i in range(4)]
    extra = positions([BAR_TICKS, BAR_TICKS + 960, 5 * BAR_TICKS, 9 * BAR_TICKS, 13 * BAR_TICKS])
    audio = place(16 * BAR, [(i * 4 * BAR, pad) for i in range(4)])
    grid = analyze.Grid(positions=positions(ticks) + extra, **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert result.mode == "windows"


def test_phrase_tail_is_kept() -> None:
    phrase = pattern(8)
    tail = hit(500, 12000, 9)
    events = [(0, phrase), (8 * BAR, phrase), (16 * BAR, tail)]
    audio = place(24 * BAR, events)
    grid = analyze.Grid(positions=positions([0, 8 * BAR_TICKS]), **GRID)
    result = analyze.analyze(audio, SR, grid)
    assert len(result.samples) == 1
    assert len(result.tails) == 1
    assert result.tails[0].start == 16 * BAR


def test_long_event_is_not_cut() -> None:
    t = np.arange(3 * BAR) / SR
    impact = np.random.default_rng(4).normal(0, 0.4, len(t)) * np.exp(-t * 1.5) + 0.2 * np.sin(2 * np.pi * 200 * t) * np.exp(-t)
    ticks = [0, 8 * BAR_TICKS, 16 * BAR_TICKS]
    audio = place(24 * BAR, [(tick * 25, impact) for tick in ticks])
    result = analyze.analyze(audio, SR, analyze.Grid(positions=positions(ticks), **GRID))
    assert result.mode == "events"
    assert len(result.samples) == 1
    sample = result.samples[0]
    assert sample.end - sample.start > 2.5 * BAR


def test_monophonic_notes() -> None:
    t = np.arange(BAR) / SR
    audio = stereo(np.tile(0.4 * np.sin(2 * np.pi * 110 * t) * np.exp(-t), 4))
    notes = [
        analyze.Note(0, 45, 100, 960),
        analyze.Note(BAR_TICKS, 45, 100, 3000),
        analyze.Note(2 * BAR_TICKS, 45, 100, 960),
        analyze.Note(3 * BAR_TICKS, 57, 100, 960),
    ]
    result = analyze.analyze(audio, SR, analyze.Grid(positions=[], bpm=120.0, notes=notes))
    assert result.mode == "notes"
    assert result.polyphony == 1
    assert result.base is not None
    assert result.base.pitch == 45
    assert result.base.start == BAR
    assert abs(result.base.measured_pitch - 45) < 0.5


def test_polyphony_is_reported() -> None:
    audio = stereo(np.ones(BAR) * 0.1)
    notes = [analyze.Note(0, 45, 100, 960), analyze.Note(480, 52, 100, 960)]
    result = analyze.analyze(audio, SR, analyze.Grid(positions=[], bpm=120.0, notes=notes))
    assert result.polyphony == 2
