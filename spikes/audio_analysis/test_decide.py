"""Решение по дорожке на синтетике с известной структурой."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402
import decide  # noqa: E402

SR = 48000
BAR = 96000
BAR_TICKS = 3840


def phrase(bars: int, seed: int) -> np.ndarray:
    """Плотная фраза, у каждого зерна своя высота: разные семена почти не коррелируют."""
    rng = np.random.default_rng(seed)
    out = np.zeros(bars * BAR)
    step = BAR // 8
    t = np.arange(step) / SR
    for index in range(bars * 8):
        freq = rng.uniform(200, 2000)
        out[index * step : (index + 1) * step] = np.sin(2 * np.pi * freq * t) * np.exp(-t * 6) * 0.5
    return out


def track(pieces: list[np.ndarray | None], bars: int) -> np.ndarray:
    size = bars * BAR
    out = np.zeros(len(pieces) * size)
    for index, piece in enumerate(pieces):
        if piece is not None:
            out[index * size : index * size + len(piece)] = piece
    return np.stack([out, out * 0.9], axis=1)


def grid(tick: int = 0) -> analyze.Grid:
    return analyze.Grid([analyze.Position(tick)], 120.0)


def run(audio: np.ndarray, value: float = decide.DEFAULT, start: int = 0) -> decide.Decision:
    return decide.cut(decide.measure(audio, SR, grid(start)), value)


def test_exact_loop_is_one_piece() -> None:
    base = phrase(2, 1)
    result = run(track([base] * 6, 2))
    assert (result.window_bars, len(result.groups), result.verdict) == (2, 1, "clean")
    assert result.confidence == 1.0


def test_two_equal_breaks_and_other_give_two_pieces() -> None:
    first, second = phrase(2, 1), phrase(2, 2)
    result = run(track([first, None, first, None, second, None], 2))
    assert len(result.groups) == 2
    assert sorted(len(g.members) for g in result.groups) == [1, 2]


def test_louder_repeat_is_same_piece() -> None:
    base = phrase(2, 1)
    assert len(run(track([base, base * 0.5, base], 2)).groups) == 1


def test_inverted_polarity_is_different_piece() -> None:
    base = phrase(2, 1)
    assert len(run(track([base, -base, base, base], 2), 0.3).groups) == 2


def test_short_difference_is_not_lost_in_long_window() -> None:
    base = phrase(8, 1)
    variant = base.copy()
    variant = base.copy()
    variant[60000:62400] += phrase(1, 9)[:2400]
    value, where = decide.difference(variant, base, 2400)
    assert value > -20
    assert where == 60000


def test_decisiveness_only_merges() -> None:
    first, other = phrase(1, 1), phrase(1, 2)
    near = first.copy()
    near[:4800] *= 0.9
    measured = decide.measure(track([first, near, other, first, first, first], 1), SR, grid())
    counts = [len(decide.cut(measured, value).groups) for value in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == 3
    assert counts[-1] == 1


def test_right_edge_keeps_one_piece_with_low_confidence() -> None:
    first, other = phrase(2, 1), phrase(2, 2)
    result = run(track([first, first, other, first], 2), 1.0)
    assert len(result.groups) == 1
    assert result.confidence < 0.3
    assert result.verdict == "lossy"


def test_no_repeats_gives_one_long_fragment_and_warning() -> None:
    result = run(track([phrase(8, seed) for seed in range(1, 8)], 8))
    assert result.verdict == "uncut"
    assert (result.window_bars, len(result.groups)) == (8, 1)
    assert result.confidence < 0.3
    assert result.coverage < 0.2
    assert len(result.uncovered) == 6


def test_track_without_repeats_opens_up_to_the_left() -> None:
    measured = decide.measure(track([phrase(8, seed) for seed in range(1, 8)], 8), SR, grid())
    counts = [len(decide.cut(measured, value).groups) for value in (0.0, 0.25, decide.DEFAULT, 1.0)]
    assert counts == sorted(counts, reverse=True)
    assert (counts[0], counts[-1]) == (7, 1)


def test_exact_repeat_merges_even_on_track_without_repeats() -> None:
    pieces = [phrase(8, seed) for seed in range(1, 8)]
    measured = decide.measure(track(pieces + [pieces[0]], 8), SR, grid())
    assert len(decide.cut(measured, 0.0).groups) == 7


def test_window_does_not_depend_on_decisiveness() -> None:
    first, other = phrase(2, 1), phrase(2, 2)
    measured = decide.measure(track([first, first, other, first], 2), SR, grid())
    assert {decide.cut(measured, value).window_bars for value in (0.0, 0.5, decide.DEFAULT, 1.0)} == {2}


def test_confidence_follows_widest_pair() -> None:
    distances = np.array([[0, -30, -30], [-30, 0, -10], [-30, -10, 0.0]])
    item = decide.Layout(1, [0, BAR, 2 * BAR], distances, np.zeros((3, 3), dtype=int), [BAR, 2 * BAR, 3 * BAR], decide.tree_of(distances))
    result = decide.cut(decide.Measured([item], SR, BAR), decide.DEFAULT)
    assert result.confidence == decide.confidence_of(-10)


def test_start_skips_silent_region() -> None:
    first, other = phrase(2, 1), phrase(2, 2)
    audio = np.r_[np.zeros((3 * BAR, 2)), track([first, first, other, first], 2)]
    result = run(audio)
    assert result.window_bars == 2
    assert result.groups[0].start == 3 * BAR


def test_windows_start_at_first_sound() -> None:
    base = phrase(2, 1)
    pieces = track([None, base, base, base], 2)
    shifted = np.r_[np.zeros((BAR, 2)), pieces]
    result = run(shifted, start=3 * BAR_TICKS)
    assert len(result.groups) == 1
    assert result.groups[0].start == 3 * BAR


def test_start_from_notes_when_no_regions() -> None:
    notes = [analyze.Note(2 * BAR_TICKS, 60, 100, 240)]
    assert decide.first_position(analyze.Grid([], 120.0, notes), SR) == 2 * BAR


def test_short_tail_stays_with_previous_piece() -> None:
    base = phrase(2, 1)
    audio = track([base, None, base, None], 2)
    audio[2 * BAR : 2 * BAR + 500] = 0.2
    result = run(audio)
    assert [m.bar for m in result.groups[0].members] == [1.0, 5.0]
    assert result.groups[0].end == 2 * BAR + 500


def test_tail_of_other_member_is_reported_as_lost(tmp_path: Path) -> None:
    base = phrase(2, 1)
    audio = track([base, None, base, None], 2)
    audio[6 * BAR : 6 * BAR + 500] = 0.2
    result = run(audio)
    assert result.verdict == "lossy"
    assert result.uncovered == [5.0]
    assert [m.lost_tail for m in result.groups[0].members] == [0, 500]
    folder = decide.write_version(tmp_path, audio, SR, result, "ELA", "SY", "Saw")
    assert "потерян хвост 500" in (folder / "report.md").read_text(encoding="utf-8")


def test_tail_is_in_wav_file(tmp_path: Path) -> None:
    base = phrase(2, 1)
    audio = track([base, None, base, None], 2)
    audio[2 * BAR : 2 * BAR + 500] = 0.2
    folder = decide.write_version(tmp_path, audio, SR, run(audio), "ELA", "SY", "Saw")
    assert sf.info(str(folder / "ELA_SY_Saw_01.wav")).frames == 2 * BAR + 500


def test_cut_sound_fades_at_edges() -> None:
    piece = np.full((BAR, 2), 0.5)
    out = decide.faded(piece, SR)
    assert abs(out[0, 0]) < 0.01 and abs(out[-1, 0]) < 0.01
    assert out[BAR // 2, 0] == 0.5
    assert len(out) == BAR
    assert piece[0, 0] == 0.5


def test_silent_edge_is_not_faded() -> None:
    piece = np.full((BAR, 2), 0.5)
    piece[:480] = piece[-480:] = analyze.SILENCE * 0.5
    assert np.array_equal(decide.faded(piece, SR), piece)


def test_attack_from_zero_is_not_faded() -> None:
    piece = np.zeros((BAR, 2))
    piece[:96, 0] = piece[:96, 1] = np.linspace(0, 0.02, 96)
    assert np.array_equal(decide.faded(piece, SR)[:96], piece[:96])


def test_silent_windows_are_skipped() -> None:
    base = phrase(2, 1)
    result = run(track([base, None, None, base], 2))
    assert [m.bar for m in result.groups[0].members] == [1.0, 7.0]


def test_replaced_variant_is_reported_with_place() -> None:
    base = phrase(1, 1)
    variant = base.copy()
    variant[60000:64800] += phrase(1, 9)[:4800]
    result = run(track([base, base, base, variant], 1), 1.0)
    replaced = [m for m in result.groups[0].members if m.difference_db > decide.CLEAN_DB]
    assert [m.bar for m in replaced] == [4.0]
    assert 4.6 <= replaced[0].worst_bar < 4.7


def test_replaced_bar_is_in_report(tmp_path: Path) -> None:
    base = phrase(1, 1)
    variant = base.copy()
    variant[60000:64800] += phrase(1, 9)[:4800]
    audio = track([base, base, base, variant], 1)
    folder = decide.write_version(tmp_path, audio, SR, run(audio, 1.0), "ELA", "SY", "Saw")
    text = (folder / "report.md").read_text(encoding="utf-8")
    assert "- Такт 4.0: заменён" in text
    assert "Не покрыты точно такты: 4.0." in text


def test_end_of_piece_is_compared_when_not_multiple_of_frame() -> None:
    base = phrase(1, 1)[:9700]
    variant = base.copy()
    variant[-100:] += 0.5
    value, where = decide.difference(variant, base, 600)
    assert value > -20
    assert where == 9600


def test_no_correlation_has_no_place() -> None:
    base = phrase(1, 1)
    assert decide.difference(-base, base, 600) == (decide.CEILING_DB, -1)

def test_versions_keep_old_files_and_refusal(tmp_path: Path) -> None:
    audio = track([phrase(2, 1), phrase(2, 2), phrase(2, 1), phrase(2, 1)], 2)
    measured = decide.measure(audio, SR, grid())
    args = dict(code="ELA", group="SY", name="Saw")
    first = decide.write_version(tmp_path, audio, SR, decide.cut(measured, decide.DEFAULT), **args)
    second = decide.write_version(tmp_path, audio, SR, decide.cut(measured, 1.0), refusal="Слишком много", **args)
    assert (first.name, second.name) == ("v1", "v2")
    assert sorted(p.name for p in first.glob("*.wav")) == ["ELA_SY_Saw_01.wav", "ELA_SY_Saw_02.wav"]
    assert [p.name for p in second.glob("*.wav")] == ["ELA_SY_Saw_01.wav"]
    saved = json.loads((second / "decision.json").read_text(encoding="utf-8"))
    assert saved["version"] == 2 and saved["refusal"] == "Слишком много" and saved["decisiveness"] == 1.0
    assert len(saved["groups"][0]["members"]) == 4
    assert "Слишком много" in (second / "report.md").read_text(encoding="utf-8")
    info = sf.info(str(first / "ELA_SY_Saw_01.wav"))
    assert (info.subtype, info.channels, info.frames) == ("PCM_24", 2, 2 * BAR)
