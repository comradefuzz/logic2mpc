"""Сценарии из docs/analysis.md на реальном проекте.

Пути задаются переменными окружения, без них тесты пропускаются:

    LOGIC2MPC_PROJECT   проект .logicx
    LOGIC2MPC_EXPORT    папка с экспортом дорожек
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import soundfile as sf

from logic2mpc.adapters import logic
from logic2mpc.core.analysis import analyze_track
from logic2mpc.core.cycle import find_cycle
from logic2mpc.core.model import BAR, Cut

PROJECT = os.environ.get("LOGIC2MPC_PROJECT")

EXPORT = os.environ.get("LOGIC2MPC_EXPORT")

needs_project = pytest.mark.skipif(not PROJECT, reason="нет LOGIC2MPC_PROJECT")
needs_export = pytest.mark.skipif(not (PROJECT and EXPORT), reason="нет LOGIC2MPC_PROJECT или LOGIC2MPC_EXPORT")


def track(name: str):
    song = logic.read_project(Path(PROJECT))
    return next(t for t in song.tracks if t.name == name)


def cut_of(name: str) -> Cut:
    song = logic.read_project(Path(PROJECT))
    item = next(t for t in song.tracks if t.name == name)
    files = {int(p.name.split("_")[0]): p for p in Path(EXPORT).glob("*.wav")}
    audio, sr = sf.read(files[item.row + 1], always_2d=True)
    return analyze_track(item, audio, sr, song.bpm)


FRAMES_PER_BAR = 96000


@needs_project
def test_bass_oliver_cycle_is_eight_bars() -> None:
    assert find_cycle(track("Bass Oliver").midi_regions).bars == 8


@needs_project
def test_fire_glow_is_eight_bar_loop_from_bar_seventeen() -> None:
    cycle = find_cycle(track("SY - Fire Glow").midi_regions)
    assert cycle.bars == 8
    assert cycle.start == 16 * BAR
    assert len(cycle.passes) == 9


@needs_project
def test_kick_regions_are_read() -> None:
    regions = track("DS_LENNO_drum_kick_nerve").audio_regions
    assert sum(not r.muted for r in regions) == 320


@needs_export
def test_bass_oliver_sample_is_from_bar_seventeen() -> None:
    cut = cut_of("Bass Oliver")
    assert cut.pieces[0].start == 16 * FRAMES_PER_BAR
    assert cut.lost_bars == [9.0, 49.0, 97.0]


@needs_export
def test_fire_glow_sample_is_from_bar_sixty_five() -> None:
    assert cut_of("SY - Fire Glow").pieces[0].start == 64 * FRAMES_PER_BAR


@needs_export
@pytest.mark.parametrize(("name", "count"), [
    ("Audio 48", 1),
    ("CC_120_drums_fills_buildup_snare_01", 1),
    ("Lothar BM", 1),
    ("MO_WS_BS_Normal_Reese", 3),
    ("RKU_IOG_Fx_Rise_Excellent_Em", 2),
    ("PN - Ambient Piano", 1),
    ("SY - Interesting Sines", 1),
    ("ZEN_STR_120_lead_synth_missing_Em", 3),
    ("LD Saw Harm", 4),
    ("Fill JaBouncy", 2),
])
def test_listening_decisions(name: str, count: int) -> None:
    assert len(cut_of(name).pieces) == count
