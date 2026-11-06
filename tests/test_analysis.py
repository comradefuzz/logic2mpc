"""Правила анализа из docs/analysis.md на синтетических дорожках."""
from __future__ import annotations

import numpy as np
import pytest

from logic2mpc.core.analysis import analyze_track, join_regions, same_slice
from logic2mpc.core.cycle import common_pass, find_cycle, fit, period
from logic2mpc.core.model import BAR, AudioRegion, MidiRegion, Note, Track
from logic2mpc.core.signal import alike

SR = 48000
BPM = 120.0
FRAMES = SR * 2  # такт при 120 BPM


def note(tick: int, pitch: int = 60, length: int = 240) -> Note:
    return Note(tick, pitch, 100, length)


def phrase(seed: int, count: int = 16) -> list[Note]:
    """Разные фразы на 4 такта с фиксированной сеткой."""
    rng = np.random.default_rng(seed)
    return [note(i * 960, int(rng.integers(48, 72))) for i in range(count)]


def audio_track(regions: list[AudioRegion], name: str = "Audio") -> Track:
    return Track(1, name, "Drums", [], regions)


def midi_track(regions: list[MidiRegion], name: str = "Synth") -> Track:
    return Track(1, name, "Synth", regions, [])


def stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono], axis=1)


def burst(rng: np.random.Generator, size: int) -> np.ndarray:
    return rng.normal(0, 0.4, size) * np.exp(-np.arange(size) / (size / 6))


def test_an010_identical_hits_give_one_sample() -> None:
    rng = np.random.default_rng(1)
    hit = burst(rng, 6000)
    mono = np.zeros(FRAMES * 4)
    regions = []
    for i in range(8):
        start = i * FRAMES // 2
        mono[start : start + len(hit)] += hit
        regions.append(AudioRegion(i * BAR // 2))
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    assert cut.rule == "AN-010"
    assert len(cut.pieces) == 1
    assert cut.pieces[0].lead > 0
    assert sorted(o.tick for o in cut.pieces[0].occurrences) == [r.tick for r in regions]


def test_an010_keeps_gain_of_each_hit() -> None:
    rng = np.random.default_rng(2)
    hit = burst(rng, 6000)
    mono = np.zeros(FRAMES * 2)
    regions = []
    for i, gain in enumerate((1.0, 0.5, 1.0, 0.25)):
        start = i * FRAMES // 2
        mono[start : start + len(hit)] += gain * hit
        regions.append(AudioRegion(i * BAR // 2))
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    gains = sorted(o.gain / max(x.gain for x in cut.pieces[0].occurrences) for o in cut.pieces[0].occurrences)
    assert gains == pytest.approx([0.25, 0.5, 1.0, 1.0], abs=0.02)


def test_an011_single_region_stays_whole_even_with_many_false_onsets() -> None:
    rng = np.random.default_rng(3)
    size = FRAMES * 3
    sweep = rng.normal(0, 0.3, size) * np.linspace(1, 0, size)
    mono = np.r_[sweep, np.zeros(FRAMES)]
    cut = analyze_track(audio_track([AudioRegion(0)]), stereo(mono), SR, BPM)
    assert cut.rule == "AN-011"
    assert len(cut.pieces) == 1
    assert cut.pieces[0].start == 0
    assert cut.pieces[0].end == pytest.approx(size, abs=SR)
    assert [o.tick for o in cut.pieces[0].occurrences] == [0]


def test_an012_loop_length_gives_piece_length() -> None:
    rng = np.random.default_rng(4)
    loop = rng.normal(0, 0.2, FRAMES * 2)
    mono = np.tile(loop, 4)
    region = AudioRegion(0, loop_end=8 * BAR, length=2 * BAR)
    cut = analyze_track(audio_track([region]), stereo(mono), SR, BPM)
    assert cut.rule == "AN-012"
    assert len(cut.pieces) == 1
    assert cut.pieces[0].end - cut.pieces[0].start == FRAMES * 2
    assert [o.tick for o in cut.pieces[0].occurrences] == [0, 2 * BAR, 4 * BAR, 6 * BAR]


def test_an012_an061_unfinished_pass_is_short_and_reported() -> None:
    loop = np.random.default_rng(15).normal(0, 0.2, FRAMES * 2)
    mono = np.tile(loop, 4)
    region = AudioRegion(0, loop_end=7 * BAR, length=2 * BAR)
    cut = analyze_track(audio_track([region]), stereo(mono), SR, BPM)
    assert [o.length for o in cut.pieces[0].occurrences] == [None, None, None, BAR]
    assert cut.lost_bars == [7.0]


def noise_hit(seed: int, size: int = 12000) -> np.ndarray:
    raw = np.random.default_rng(seed).normal(0, 0.4, size)
    coloured = np.convolve(raw, np.ones(12) / 3, mode="same")  # у шума свой спектр
    return coloured * np.exp(-np.arange(size) / 2000)


def test_an015_noise_hits_with_same_spectrum_are_one_sample() -> None:
    assert alike(noise_hit(1), noise_hit(2), SR)


def test_an015_different_sounds_stay_different() -> None:
    low = np.sin(np.arange(12000) * 0.01) * np.exp(-np.arange(12000) / 2000)
    assert not alike(noise_hit(1), low, SR)


def test_an009_regions_back_to_back_in_file_join() -> None:
    joined, merged = join_regions([
        AudioRegion(0, length=3 * BAR, source=1, offset=0, frames=300), AudioRegion(3 * BAR, length=BAR, source=1, offset=300, frames=100),
        AudioRegion(8 * BAR, length=BAR, source=1, offset=300, frames=100),
    ])
    assert merged == {0}
    assert [(r.tick, r.length, r.frames) for r in joined] == [(0, 4 * BAR, 400), (8 * BAR, BAR, 100)]


def test_an009_repeat_placed_back_to_back_is_not_joined() -> None:
    regions = [AudioRegion(0, length=8 * BAR, source=1, offset=0, frames=800), AudioRegion(8 * BAR, length=8 * BAR, source=1, offset=0, frames=800)]
    assert join_regions(regions)[1] == set()


def test_an009_other_file_does_not_join() -> None:
    regions = [AudioRegion(0, length=BAR, source=1, offset=0, frames=100), AudioRegion(BAR, length=BAR, source=2, offset=100, frames=100)]
    assert join_regions(regions)[1] == set()


def test_an009_unknown_slice_does_not_join() -> None:
    assert join_regions([AudioRegion(0, length=BAR, source=1), AudioRegion(BAR, length=BAR, source=1)])[1] == set()


def test_an015_same_slice_from_project_data() -> None:
    whole = AudioRegion(0, source=1, offset=0, frames=96000)
    assert same_slice(AudioRegion(0, source=1, offset=6000, frames=90000), whole)
    assert not same_slice(AudioRegion(0, source=1, offset=80000, frames=16000), whole)
    assert not same_slice(AudioRegion(0, source=2, offset=6000, frames=90000), whole)


def test_an015_different_sound_with_same_slice_merges_without_audio_check() -> None:
    mono = np.zeros(FRAMES * 8)
    mono[:12000] = noise_hit(1)
    mono[FRAMES * 4 : FRAMES * 4 + 12000] = np.sin(np.arange(12000) * 0.01) * np.exp(-np.arange(12000) / 2000)
    regions = [
        AudioRegion(0, length=BAR, source=1, offset=0, frames=96000),
        AudioRegion(4 * BAR, length=BAR, source=1, offset=0, frames=96000),
    ]
    assert len(analyze_track(audio_track(regions), stereo(mono), SR, BPM).pieces) == 1


def test_an014_cut_riser_is_one_sample_and_tail_is_another() -> None:
    rng = np.random.default_rng(20)
    size = FRAMES * 4
    rise = rng.normal(0, 0.3, size) * np.linspace(0.1, 1, size)
    tail = rise[-FRAMES:]
    mono = np.zeros(FRAMES * 16)
    mono[:size] = rise
    mono[FRAMES * 10 : FRAMES * 11] = tail
    regions = [
        AudioRegion(0, length=3 * BAR, source=1, offset=0, frames=3 * FRAMES),
        AudioRegion(3 * BAR, length=BAR, source=1, offset=3 * FRAMES, frames=FRAMES),
        AudioRegion(10 * BAR, length=BAR, source=1, offset=3 * FRAMES, frames=FRAMES),
    ]
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    assert len(cut.pieces) == 2
    assert cut.pieces[0].end == pytest.approx(size, abs=SR)


def test_an014_noise_regions_merge_into_one() -> None:
    mono = np.zeros(FRAMES * 8)
    mono[: 12000] = noise_hit(1)
    mono[FRAMES * 4 : FRAMES * 4 + 12000] = noise_hit(2)
    regions = [AudioRegion(0, length=BAR, source=1), AudioRegion(4 * BAR, length=BAR, source=1)]
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    assert len(cut.pieces) == 1
    assert sorted(o.tick for o in cut.pieces[0].occurrences) == [0, 4 * BAR]


def test_an041_short_sound_is_not_merged_by_spectrum() -> None:
    mono = np.zeros(FRAMES * 8)
    mono[:48000] = noise_hit(1, 48000) / np.exp(-np.arange(48000) / 2000) * np.linspace(1, 0, 48000) * 0.01
    mono[FRAMES * 4 : FRAMES * 4 + 12000] = noise_hit(2, 12000)
    regions = [AudioRegion(0, length=BAR, source=1), AudioRegion(4 * BAR, length=BAR, source=1)]
    assert len(analyze_track(audio_track(regions), stereo(mono), SR, BPM).pieces) == 2


def test_an013_other_tracks_go_to_window_comparison() -> None:
    rng = np.random.default_rng(5)
    bar_a = rng.normal(0, 0.2, FRAMES)
    bar_b = bar_a.copy()
    bar_b[FRAMES // 2 : FRAMES // 2 + SR // 10] = rng.normal(0, 0.9, SR // 10)  # короткое отличие
    mono = np.r_[bar_a, bar_a, bar_b, bar_a]
    regions = [AudioRegion(0), AudioRegion(2 * BAR)]
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    assert cut.rule == "AN-013"
    assert cut.cycle_bars == 1
    assert sorted(len(p.occurrences) for p in cut.pieces) == [1, 3]


def test_an020_an021_region_sequence_gives_cycle_with_different_sound() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    rng = np.random.default_rng(6)
    mono = rng.normal(0, 0.2, FRAMES * 32)  # звук каждого прохода разный
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.rule == "AN-021"
    assert cut.cycle_bars == 8
    assert len(cut.pieces) == 1
    assert [o.tick for o in cut.pieces[0].occurrences] == [i * 8 * BAR for i in range(4)]


def test_an021_regions_differing_only_in_note_length_are_one_type() -> None:
    a = phrase(1)
    long = [Note(n.tick, n.pitch, n.velocity, n.length * 2) for n in a]
    other = phrase(2)
    regions = [
        MidiRegion(0, a), MidiRegion(4 * BAR, other),
        MidiRegion(8 * BAR, long), MidiRegion(12 * BAR, other),
    ]
    cycle = find_cycle(regions)
    assert cycle.source == "AN-021"
    assert cycle.bars == 8


def test_an021_cycle_starts_on_song_grid_when_region_is_there() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion((4 + 4 * i) * BAR, b if i % 2 else a) for i in range(8)]
    # Партия начинается с такта 5, но сетка цикла идёт от такта 1: первый проход с такта 9.
    cycle = find_cycle(regions)
    assert cycle.bars == 8
    assert cycle.start == 8 * BAR


def test_an021_cycle_starts_on_region_when_grid_is_empty() -> None:
    a = phrase(1, 4)
    regions = [MidiRegion((3 + 8 * i) * BAR, a) for i in range(4)]
    cycle = find_cycle(regions)
    assert cycle.bars == 8
    assert cycle.start == 3 * BAR


def test_an022_core_finds_cycle_inside_long_region() -> None:
    pattern = phrase(1)
    notes = [Note(n.tick + i * 4 * BAR, n.pitch, n.velocity, n.length) for i in range(6) for n in pattern]
    cycle = find_cycle([MidiRegion(0, notes)])
    assert cycle.source == "AN-022"
    assert cycle.bars == 4


def test_an022_broken_pass_and_extra_notes_stay_in_cycle() -> None:
    pattern = phrase(1)
    notes = []
    for i in range(6):
        for n in pattern:
            if i == 3 and n.tick >= 3 * BAR:  # недоигранный проход, 75% ядра
                continue
            notes.append(Note(n.tick + i * 4 * BAR, n.pitch, n.velocity, n.length))
    notes += [Note(4 * BAR + 120, 90 + i, 100, 240) for i in range(5)]
    cycle = find_cycle([MidiRegion(0, notes)])
    assert cycle.bars == 4
    assert len(cycle.passes) == 6


def test_an022_pass_below_seventy_percent_is_not_in_cycle() -> None:
    pattern = phrase(1)
    notes = []
    for i in range(6):
        for n in pattern:
            if i == 3 and n.tick >= 2 * BAR:  # половина ядра
                continue
            notes.append(Note(n.tick + i * 4 * BAR, n.pitch, n.velocity, n.length))
    played = sorted((n.tick, n.pitch, n.length) for n in notes)
    cycle = fit(played, 4, 0, "AN-022")
    assert 3 * 4 * BAR not in cycle.passes
    assert len(cycle.passes) == 5


@pytest.mark.parametrize(("kept", "inside"), [(14, True), (13, False)])
def test_an022_pass_threshold_is_seventy_percent(kept: int, inside: bool) -> None:
    pattern = [note(i * 192) for i in range(20)]
    notes = []
    for i in range(6):
        played = pattern[:kept] if i == 3 else pattern
        notes += [Note(n.tick + i * 4 * BAR, n.pitch, n.velocity, n.length) for n in played]
    cycle = fit(sorted((n.tick, n.pitch, n.length) for n in notes), 4, 0, "AN-022")
    assert (3 * 4 * BAR in cycle.passes) is inside


def test_an021_two_equal_regions_among_different_are_not_a_cycle() -> None:
    regions = [MidiRegion(0, phrase(1, 4)), MidiRegion(BAR, phrase(1, 4))]
    regions += [MidiRegion((4 + i * 4) * BAR, phrase(10 + i)) for i in range(10)]
    assert period(regions) is None


def test_an060_cycle_keeps_full_velocity_when_sound_differs() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    mono = np.random.default_rng(12).normal(0, 0.2, FRAMES * 32)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert {o.gain for o in cut.pieces[0].occurrences} == {1.0}


def test_an061_passes_different_from_sample_are_reported() -> None:
    a, b = phrase(1), phrase(2)
    changed = [*a[:-1], note(a[-1].tick, 100)]
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    regions[6] = MidiRegion(24 * BAR, changed)
    mono = np.random.default_rng(13).normal(0, 0.2, FRAMES * 32)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.replaced_bars == [25.0]


def test_silent_sample_pass_does_not_lose_cycle() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    mono = np.random.default_rng(16).normal(0, 0.2, FRAMES * 32)
    mono[: FRAMES * 8] = 0
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.pieces[0].start == 8 * FRAMES
    assert cut.lost_bars == [1.0]
    assert len(cut.pieces[0].occurrences) == 3


def test_an020a_passes_before_found_start_stay_in_cycle() -> None:
    a = phrase(1, 8)
    regions = [MidiRegion(36 * BAR, a), MidiRegion(76 * BAR, a), MidiRegion(84 * BAR, a)]
    cycle = find_cycle(regions)
    assert 36 * BAR in cycle.passes


def test_an030_sample_is_whole_pass_followed_by_same() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    mono = np.random.default_rng(21).normal(0, 0.2, FRAMES * 32)
    mono[int(FRAMES * 7) : FRAMES * 8] = 0  # первый проход обрезан аранжировкой
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.pieces[0].start == 8 * FRAMES


def test_an030_prefers_pass_repeated_right_after() -> None:
    notes = [(i * 8 * BAR, 60, 240) for i in (0, 3, 4)]
    extra = [(i * 8 * BAR + BAR, 61, 240) for i in (0, 3, 4)]
    other = [(1 * 8 * BAR, 72, 240)]
    played = sorted([*notes, *extra, *other])
    assert common_pass(played, [0, 8 * BAR, 24 * BAR, 32 * BAR], 8 * BAR) == 24 * BAR


def test_an033_unfinished_pass_gets_short_note_and_is_lost() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    mono = np.random.default_rng(22).normal(0, 0.2, FRAMES * 32)
    mono[FRAMES * 7 : FRAMES * 8] = 0
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    first = cut.pieces[0].occurrences[0]
    assert first.tick == 0
    assert first.length == pytest.approx(7 * BAR, abs=10)
    assert 1.0 in cut.lost_bars


def test_an034_exact_pass_off_grid_replaces_overlapping_passes() -> None:
    a = phrase(1)
    body = a + [Note(n.tick + 4 * BAR, n.pitch + 1, n.velocity, n.length) for n in a]
    regions = [MidiRegion(i * 8 * BAR, body) for i in range(10)]
    regions.append(MidiRegion(80 * BAR, phrase(5, 8)))  # регион на 3 такта, дальше фраза со сдвигом
    regions.append(MidiRegion(84 * BAR, body))
    mono = np.random.default_rng(23).normal(0, 0.2, FRAMES * 96)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert len(cut.pieces) == 1
    assert 84 * BAR in [o.tick for o in cut.pieces[0].occurrences]
    assert 81.0 in cut.lost_bars


def test_an023_silence_between_regions_is_not_in_sample() -> None:
    regions = [
        MidiRegion(0, phrase(1)), MidiRegion(40 * BAR, phrase(2)),
        MidiRegion(48 * BAR, [*phrase(1)]), MidiRegion(70 * BAR, phrase(3, 3)),
    ]
    mono = np.zeros(FRAMES * 80)
    rng = np.random.default_rng(24)
    for start, bars in ((0, 8), (40, 16), (70, 2)):
        mono[start * FRAMES : (start + bars) * FRAMES] = rng.normal(0, 0.2, bars * FRAMES)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.rule == "AN-023"
    assert len(cut.pieces) == 3
    assert cut.pieces[0].end <= 8 * FRAMES
    assert sorted(len(p.occurrences) for p in cut.pieces) == [1, 1, 2]


def test_an023_near_copy_is_reported_as_replaced() -> None:
    first = phrase(1)
    near = [note(0, 100), *first[1:]]
    regions = [MidiRegion(0, first), MidiRegion(40 * BAR, near), MidiRegion(60 * BAR, phrase(2))]
    mono = np.random.default_rng(31).normal(0, 0.2, FRAMES * 70)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.replaced_bars == [41.0]


def test_an023_limit_of_pieces_goes_to_losses() -> None:
    regions = [MidiRegion(i * 20 * BAR, phrase(i + 1)) for i in range(5)]
    mono = np.random.default_rng(32).normal(0, 0.2, FRAMES * 110)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert len(cut.pieces) == 4
    assert len(cut.lost_bars) == 1


def test_an023_note_before_region_moves_start() -> None:
    region = MidiRegion(4 * BAR, [Note(-100, 60, 100, 240), *phrase(1)[1:]])
    mono = np.random.default_rng(33).normal(0, 0.2, FRAMES * 12)
    cut = analyze_track(midi_track([region]), stereo(mono), SR, BPM)
    assert cut.pieces[0].start == 3 * FRAMES


def test_an033_hit_ending_early_gets_short_note() -> None:
    rng = np.random.default_rng(34)
    long_hit = rng.normal(0, 0.3, FRAMES)
    mono = np.zeros(FRAMES * 8)
    regions = []
    for i in range(4):
        start = i * 2 * FRAMES
        mono[start : start + (FRAMES // 4 if i == 3 else FRAMES)] = long_hit[: FRAMES // 4 if i == 3 else FRAMES]
        regions.append(AudioRegion(i * 2 * BAR))
    cut = analyze_track(audio_track(regions), stereo(mono), SR, BPM)
    short = [o for p in cut.pieces for o in p.occurrences if o.length]
    assert [o.tick for o in short] == [6 * BAR]
    assert cut.lost_bars == [7.0]


def test_an004_audio_on_midi_track_is_reported() -> None:
    track = Track(1, "Mixed", "Synth", [MidiRegion(0, phrase(1))], [AudioRegion(0)])
    mono = np.random.default_rng(14).normal(0, 0.2, FRAMES * 4)
    assert "AN-004" in analyze_track(track, stereo(mono), SR, BPM).remark


def test_silent_track_is_reported() -> None:
    cut = analyze_track(audio_track([AudioRegion(0)]), np.zeros((FRAMES, 2)), SR, BPM)
    assert cut.pieces == []
    assert "нет звука" in cut.remark


def test_an023_single_pass_is_one_piece_with_low_confidence() -> None:
    region = MidiRegion(4 * BAR, phrase(1))
    mono = np.random.default_rng(7).normal(0, 0.2, FRAMES * 12)
    cut = analyze_track(midi_track([region]), stereo(mono), SR, BPM)
    assert cut.rule == "AN-023"
    assert len(cut.pieces) == 1
    assert cut.confidence < 0.5
    assert cut.pieces[0].start == 4 * FRAMES


def test_an030_pass_with_overlay_is_not_sample() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    # Наложение попадает в самый ранний проход.
    regions.append(MidiRegion(2 * BAR, [note(0, 100 + i) for i in range(6)]))
    mono = np.random.default_rng(8).normal(0, 0.2, FRAMES * 32)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.pieces[0].start == 8 * FRAMES


def test_an030_most_frequent_exact_variant_wins() -> None:
    a, b = phrase(1), phrase(2)
    long = [Note(n.tick, n.pitch, n.velocity, n.length * 2) for n in a]
    # Первый проход отличается длиной нот, частый вариант со второго.
    regions = [MidiRegion(0, long), MidiRegion(4 * BAR, b)]
    regions += [MidiRegion((8 + i * 4) * BAR, b if i % 2 else a) for i in range(6)]
    mono = np.random.default_rng(9).normal(0, 0.2, FRAMES * 32)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.pieces[0].start == 8 * FRAMES


def test_an003_muted_region_does_not_affect_cycle_and_is_reported() -> None:
    a, b = phrase(1), phrase(2)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    # Без Mute такой регион дал бы проход вне цикла и второй фрагмент.
    muted = MidiRegion(32 * BAR, phrase(3), muted=True)
    mono = np.random.default_rng(10).normal(0, 0.2, FRAMES * 40)
    cut = analyze_track(midi_track([*regions, muted]), stereo(mono), SR, BPM)
    audible = MidiRegion(32 * BAR, phrase(3))
    assert len(analyze_track(midi_track([*regions, audible]), stereo(mono), SR, BPM).pieces) == 2
    assert cut.cycle_bars == 8
    assert len(cut.pieces) == 1
    assert cut.muted_bars == [33.0]


def test_an040_rare_pass_becomes_variant_within_limit() -> None:
    a, b, c = phrase(1), phrase(2), phrase(3)
    regions = [MidiRegion(i * 4 * BAR, b if i % 2 else a) for i in range(8)]
    regions += [MidiRegion(32 * BAR, c), MidiRegion(36 * BAR, c)]
    mono = np.random.default_rng(11).normal(0, 0.2, FRAMES * 40)
    cut = analyze_track(midi_track(regions), stereo(mono), SR, BPM)
    assert cut.cycle_bars == 8
    assert len(cut.pieces) == 2
    assert cut.pieces[1].start == 32 * FRAMES


def test_an050_edges_are_marked_and_audio_is_not_changed() -> None:
    size = FRAMES * 2
    mono = np.sin(np.arange(size) * 0.05) * 0.5 + 0.2  # звук есть на обоих краях
    cut = analyze_track(audio_track([AudioRegion(0)]), stereo(mono), SR, BPM)
    piece = cut.pieces[0]
    assert piece.start_open is True
    assert piece.end_open is True
    assert piece.start == 0
    assert piece.end == size


def test_an050_silent_edges_are_not_marked() -> None:
    size = FRAMES
    mono = np.r_[np.zeros(100), np.hanning(size) * 0.5, np.zeros(100)]
    cut = analyze_track(audio_track([AudioRegion(0)]), stereo(mono), SR, BPM)
    assert cut.pieces[0].start_open is False
    assert cut.pieces[0].end_open is False
