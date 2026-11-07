"""S-019, правило AN-072: цвета треков и пэдов. Тесты стори, в общий набор переносятся при приёмке по разделу «Тестирование»."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from logic2mpc.adapters import xpj, xpj_spec  # noqa: E402
from logic2mpc.core.plan import Occurrence, PlanPiece, PlanTrack  # noqa: E402
from test_export import sample_plan, write_samples  # noqa: E402

CIRCLE = [
    0x55FF00, 0x00FF80, 0x00AAFF, 0x5200FF, 0xFF00FF, 0xFF4400, 0xE6FF00, 0x11FF00, 0x00FFC4, 0x0066FF, 0x6F00FF,
    0xFF00BB, 0xFF8800, 0xA2FF00, 0x00FF33, 0x00F7FF, 0x0022FF, 0xB200FF, 0xFF0077, 0xFF0000, 0xFFD500,
]


def one(name: str) -> PlanPiece:
    return PlanPiece(name, f"{name}.wav", 1.0, 3840, 1.0, [Occurrence(0)])


def track_of(row: int, *pieces: PlanPiece) -> PlanTrack:
    return PlanTrack(row, f"T{row}", "AN-010", 1.0, list(pieces))


def built(tmp_path: Path, plan) -> dict:
    write_samples(plan, tmp_path / "samples")
    return xpj.load(xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song").path).data


def pad_colours(data: dict, track: int, count: int = 8) -> list[int]:
    pads = data["tracks"][track]["program"]["programPads"]["pads"]
    return [int(str(pads[f"value{i}"])) for i in range(count)]


def test_track_palette_is_the_live2_circle_of_21() -> None:
    assert list(xpj_spec.TRACK_PALETTE) == CIRCLE
    assert [xpj_spec.track_colour(n) for n in (0, 20, 21, 42, 63)] == [0x55FF00, 0xFFD500, 0x55FF00, 0x55FF00, 0x55FF00]


def test_tracks_of_a_built_project_follow_the_circle(tmp_path: Path) -> None:
    data = built(tmp_path, sample_plan())
    assert [t["colour"] for t in data["tracks"]] == CIRCLE[: len(data["tracks"])]
    assert data["tracks"][0]["colour"] == 0x55FF00


def test_pads_of_one_logic_track_share_a_colour_and_tracks_differ(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks = [track_of(1, one("a1"), one("a2")), track_of(2, one("b1")), track_of(3, one("c1"), one("c2"))]
    colours = pad_colours(built(tmp_path, plan), 1, 7)
    assert colours == [CIRCLE[0], CIRCLE[0], CIRCLE[1], CIRCLE[2], CIRCLE[2], 0, 0]


def test_empty_pads_stay_without_colour_and_numbering_restarts_in_every_drum_track(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks = [track_of(1, one("a1"))]
    plan.groups[1].tracks = [track_of(2, one("b1"))]
    data = built(tmp_path, plan)
    assert pad_colours(data, 1, 3) == [CIRCLE[0], 0, 0] and pad_colours(data, 2, 3) == [CIRCLE[0], 0, 0]


def test_merged_and_not_exported_pieces_do_not_take_a_colour(tmp_path: Path) -> None:
    plan = sample_plan()
    merged = PlanPiece("a2", "a2.wav", 1.0, 3840, 1.0, [Occurrence(0)], merged_into="a1")
    hidden = PlanPiece("b2", "b2.wav", 1.0, 3840, 1.0, [Occurrence(0)], export=False)
    plan.groups[0].tracks = [track_of(1, one("a1"), merged), track_of(2, hidden), track_of(3, one("c1"))]
    assert pad_colours(built(tmp_path, plan), 1, 3) == [CIRCLE[0], CIRCLE[1], 0]


def test_single_pad_mode_is_set_where_pads_are_painted(tmp_path: Path) -> None:
    data = built(tmp_path, sample_plan())
    for track in data["tracks"][1:]:
        assert track["program"]["programPads"]["Universal"]["value0"] is False


def test_pad_index_is_the_pad_number_of_the_fragment(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks = [track_of(1, one("a1")), track_of(2, one("b1")), track_of(3, one("c1"))]
    data = built(tmp_path, plan)
    instruments = data["tracks"][1]["program"]["drum"]["instruments"]
    filled = [i for i, pad in enumerate(instruments) if pad["layersv"][0]["sampleFile"]]
    colours = pad_colours(data, 1, 128)
    assert filled == [0, 1, 2] and [i for i, c in enumerate(colours) if c] == filled


def test_only_circle_colours_are_written_and_other_fields_do_not_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = sample_plan()
    data = built(tmp_path / "a", plan)
    written = {t["colour"] for t in data["tracks"]} | {c for i in range(len(data["tracks"])) for c in pad_colours(data, i, 128)}
    assert written <= set(CIRCLE) | {0}
    monkeypatch.setattr(xpj, "pad_colours", lambda group: [0] * len(xpj.exported(group)))
    plain = built(tmp_path / "b", plan)
    for tr_a, tr_b in zip(data["tracks"], plain["tracks"]):
        tr_a["colour"] = tr_b["colour"] = 0
        pp_a, pp_b = tr_a["program"]["programPads"], tr_b["program"]["programPads"]
        pp_a["pads"] = pp_b["pads"] = {}
        pp_a["Universal"] = pp_b["Universal"] = {}
    assert data == plain
