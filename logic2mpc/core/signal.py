"""Обработка звука для правил анализа. Перенесено из spikes/audio_analysis, см. docs/analysis.md."""
from __future__ import annotations

import librosa
import numpy as np
from scipy.signal import correlate

from .model import PPQ

SILENCE = 10 ** (-60 / 20)
LEAD_IN = 2048
EDGE = 4
EDGE_LEVEL = SILENCE * 2
SPECTRUM_MATCH = 0.98
ENVELOPE_MATCH = 0.8


def ticks_to_frames(tick: int, bpm: float, sr: int) -> int:
    return round(tick * 60 / (PPQ * bpm) * sr)


def frames_to_ticks(position: int, bpm: float, sr: int) -> int:
    return round(position * PPQ * bpm / (60 * sr))


def find_onsets(mono: np.ndarray, sr: int, hop: int = 128) -> np.ndarray:
    """Атаки в отсчётах. Детектор даёт кадр, старт уточняется по огибающей."""
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


def sound_start(mono: np.ndarray, start: int, limit: int) -> int:
    """Начало звука, AN-066: первый отсчёт от `start` до `limit` выше порога тишины. Без звука это `start`."""
    active = np.nonzero(np.abs(mono[start:limit]) > SILENCE)[0]
    return start + int(active[0]) if active.size else start


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


def sound_print(piece: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Спектр и огибающая первой секунды."""
    power = librosa.feature.melspectrogram(y=piece[:sr], sr=sr, n_fft=2048, hop_length=256, n_mels=40)
    return np.log(power.mean(axis=1) + 1e-10), np.sqrt(power.sum(axis=0))


def alike(a: np.ndarray, b: np.ndarray, sr: int) -> bool:
    """Одинаковы на слух: шумовые звуки по форме волны не совпадают никогда. AN-015."""
    if min(len(a), len(b)) < 2048:
        return False
    spectrum_a, envelope_a = sound_print(a, sr)
    spectrum_b, envelope_b = sound_print(b, sr)
    size = min(len(envelope_a), len(envelope_b))
    with np.errstate(invalid="ignore", divide="ignore"):
        spectrum = float(np.corrcoef(spectrum_a, spectrum_b)[0, 1])
        envelope = float(np.corrcoef(envelope_a[:size], envelope_b[:size])[0, 1])
    return spectrum >= SPECTRUM_MATCH and envelope >= ENVELOPE_MATCH


def loudness_ratio(a: np.ndarray, b: np.ndarray) -> float:
    energy = float(b @ b)
    return round(float(np.sqrt(float(a @ a) / energy)), 4) if energy else 0.0


def gain_of(mono: np.ndarray, sample: np.ndarray, position: int) -> float:
    """Громкость вхождения: проекция на образец. Позиция раньше начала дорожки отсекает начало образца."""
    if position < 0:
        sample, position = sample[-position:], 0
    size = min(len(sample), len(mono) - position)
    if size <= 0:
        return 0.0
    part = sample[:size]
    energy = float(part @ part)
    return round(max(float(mono[position : position + size] @ part) / energy, 0.0), 4) if energy else 0.0


def open_edges(audio: np.ndarray, start: int, end: int) -> tuple[bool, bool]:
    """Начало и конец не в нуле: звук есть уже в крайних отсчётах. AN-050.

    Запас над порогом тишины нужен: фрагмент, обрезанный по концу звука, кончается ровно на этом пороге.
    """
    piece = audio[start:end]
    if len(piece) == 0:
        return False, False
    return bool(np.max(np.abs(piece[:EDGE])) > EDGE_LEVEL), bool(np.max(np.abs(piece[-EDGE:])) > EDGE_LEVEL)
