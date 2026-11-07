"""AN-070: правки плана пользователем, ядро без файлов."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from logic2mpc.adapters import xpj
from logic2mpc.core.edit import EditError, apply
from logic2mpc.core.model import BAR
from logic2mpc.core.plan import Group, Occurrence, Plan, PlanPiece, PlanTrack, from_json, occurrences_of, to_json
from logic2mpc.core.report import render
from logic2mpc.core.sections import Section


def piece(name: str, ticks: list[int], lead: int = 0, length: int = BAR) -> PlanPiece:
    return PlanPiece(
        name=name, file=f"{name}.wav", bar=1.0, ticks=length, confidence=1.0,
        occurrences=[Occurrence(t, 1.0) for t in ticks], lead=lead,
    )


def track(row: int, name: str, pieces: list[PlanPiece]) -> PlanTrack:
    return PlanTrack(row=row, name=name, rule="AN-010", confidence=1.0, pieces=pieces)


def make_plan() -> Plan:
    drums = [
        track(1, "Kick", [piece("ELA_DR_Kick_01", [0, 2 * BAR]), piece("ELA_DR_Kick_02", [BAR]), piece("ELA_DR_Kick_03", [3 * BAR])]),
        track(2, "Snare", [piece("ELA_DR_Snare_01", [BAR])]),
    ]
    bass = [track(3, "Bass", [piece("ELA_BS_Bass_01", [0]), piece("ELA_BS_Bass_02", [2 * BAR])])]
    synth = [track(4, "Pad", [piece("ELA_SY_Bass_01", [BAR])])]
    lead = [track(5, "Lead", [piece("ELA_SY_Lead_01", [0])])]
    return Plan(
        song="ELA", bpm=120.0, sr=48000, decisiveness=0.775,
        sections=[Section("Intro", 0, 2), Section("Main A", 2 * BAR, 2)],
        groups=[
            Group("Drums", "DR", "drum", drums), Group("Bass", "BS", "drum", bass),
            Group("Synth", "SY", "drum", synth), Group("Lead", "SY", "drum", lead),
        ],
    )


def names(plan: Plan, group: str) -> list[str]:
    return [p.name for g in plan.groups if g.name == group for t in g.tracks for p in t.pieces]


def find(plan: Plan, name: str) -> PlanPiece:
    return next(p for g in plan.groups for t in g.tracks for p in t.pieces if p.name == name)


def merge(target: str = "ELA_DR_Kick_01", sources: list[str] | None = None, row: int = 1) -> dict:
    return {"op": "merge_pieces", "track": row, "target": target, "sources": ["ELA_DR_Kick_02"] if sources is None else sources}


def test_an070_pieces_from_different_tracks_are_refused() -> None:
    with pytest.raises(EditError):
        apply(make_plan(), merge(sources=["ELA_DR_Snare_01"]))


def test_an070_target_must_be_in_the_track_and_not_in_sources() -> None:
    plan = make_plan()
    with pytest.raises(EditError):
        apply(plan, merge(target="ELA_DR_Snare_01"))
    with pytest.raises(EditError):
        apply(plan, merge(sources=["ELA_DR_Kick_01"]))
    with pytest.raises(EditError):
        apply(plan, merge(sources=[]))


@pytest.mark.smoke
def test_an070_merge_marks_sources_and_keeps_them_in_plan() -> None:
    before = make_plan()
    plan = apply(before, merge(sources=["ELA_DR_Kick_02", "ELA_DR_Kick_03"]))
    assert find(plan, "ELA_DR_Kick_02").merged_into == "ELA_DR_Kick_01"
    assert find(plan, "ELA_DR_Kick_03").merged_into == "ELA_DR_Kick_01"
    assert find(plan, "ELA_DR_Kick_01").merged_into is None
    assert all(find(plan, n).origin == "user" for n in ("ELA_DR_Kick_01", "ELA_DR_Kick_02", "ELA_DR_Kick_03"))
    assert len(names(plan, "Drums")) == len(names(before, "Drums"))
    assert find(before, "ELA_DR_Kick_02").merged_into is None


def test_an070_target_plays_occurrences_of_all_merged_pieces() -> None:
    plan = apply(make_plan(), merge(sources=["ELA_DR_Kick_02", "ELA_DR_Kick_03"]))
    kick = plan.groups[0].tracks[0]
    assert [o.tick for o in occurrences_of(kick, find(plan, "ELA_DR_Kick_01"))] == [0, BAR, 2 * BAR, 3 * BAR]
    assert [o.tick for o in occurrences_of(kick, find(plan, "ELA_DR_Kick_02"))] == [BAR]


def test_an070_merge_chain_points_to_last_target() -> None:
    plan = apply(make_plan(), merge(target="ELA_DR_Kick_02", sources=["ELA_DR_Kick_03"]))
    plan = apply(plan, merge(target="ELA_DR_Kick_01", sources=["ELA_DR_Kick_02"]))
    assert find(plan, "ELA_DR_Kick_03").merged_into == "ELA_DR_Kick_01"
    assert find(plan, "ELA_DR_Kick_02").merged_into == "ELA_DR_Kick_01"
    kick = plan.groups[0].tracks[0]
    assert len(occurrences_of(kick, find(plan, "ELA_DR_Kick_01"))) == 4


def test_an070_merged_piece_cannot_be_target_or_source_again() -> None:
    plan = apply(make_plan(), merge())
    with pytest.raises(EditError):
        apply(plan, merge(target="ELA_DR_Kick_02", sources=["ELA_DR_Kick_03"]))


@pytest.mark.smoke
def test_an070_split_restores_the_plan() -> None:
    before = make_plan()
    plan = apply(before, merge(sources=["ELA_DR_Kick_02", "ELA_DR_Kick_03"]))
    plan = apply(plan, {"op": "split_piece", "track": 1, "target": "ELA_DR_Kick_01"})
    assert [p.merged_into for p in plan.groups[0].tracks[0].pieces] == [None, None, None]
    assert [p.occurrences for p in plan.groups[0].tracks[0].pieces] == [p.occurrences for p in before.groups[0].tracks[0].pieces]
    assert len(plan.edits) == 2


def test_an070_split_of_not_merged_piece_is_refused() -> None:
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "split_piece", "track": 1, "target": "ELA_DR_Kick_01"})


def test_an070_every_edit_is_in_the_journal() -> None:
    plan = apply(make_plan(), merge())
    assert plan.edits[-1]["op"] == "merge_pieces"
    assert plan.edits[-1]["target"] == "ELA_DR_Kick_01"


def test_an070_rename_group_changes_name_only() -> None:
    plan = apply(make_plan(), {"op": "rename_group", "group": "Synth", "name": "Pads"})
    group = next(g for g in plan.groups if g.name == "Pads")
    assert group.code == "SY"
    assert names(plan, "Pads") == ["ELA_SY_Bass_01"]
    assert group.origin == "user"


@pytest.mark.parametrize("new", ["", "   ", "Drums"])
def test_an070_rename_group_refuses_empty_and_taken_name(new: str) -> None:
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "rename_group", "group": "Synth", "name": new})


def test_an070_merge_groups_keeps_first_name_and_code_and_renames_samples() -> None:
    plan = apply(make_plan(), {"op": "merge_groups", "groups": ["Drums", "Bass"]})
    assert [g.name for g in plan.groups] == ["Drums", "Synth", "Lead"]
    assert names(plan, "Drums") == [
        "ELA_DR_Kick_01", "ELA_DR_Kick_02", "ELA_DR_Kick_03", "ELA_DR_Snare_01", "ELA_DR_Bass_01", "ELA_DR_Bass_02",
    ]
    moved = find(plan, "ELA_DR_Bass_01")
    assert moved.file == "ELA_DR_Bass_01.wav"
    assert plan.groups[0].code == "DR"


def test_an070_merge_groups_needs_two_known_groups() -> None:
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "merge_groups", "groups": ["Drums"]})
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "merge_groups", "groups": ["Drums", "Nope"]})


def test_an070_merge_groups_over_128_pads_is_refused() -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [piece(f"ELA_DR_K_{i:02d}", [0]) for i in range(100)]
    plan.groups[1].tracks[0].pieces = [piece(f"ELA_BS_B_{i:02d}", [0]) for i in range(40)]
    with pytest.raises(EditError, match="128"):
        apply(plan, {"op": "merge_groups", "groups": ["Drums", "Bass"]})


def test_an070_merged_away_pieces_do_not_count_as_pads() -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [piece(f"ELA_DR_K_{i:02d}", [0]) for i in range(100)]
    plan.groups[1].tracks[0].pieces = [piece(f"ELA_BS_B_{i:02d}", [0]) for i in range(40)]
    plan = apply(plan, {"op": "merge_pieces", "track": 3, "target": "ELA_BS_B_00", "sources": [f"ELA_BS_B_{i:02d}" for i in range(1, 20)]})
    merged = apply(plan, {"op": "merge_groups", "groups": ["Drums", "Bass"]})
    assert len(merged.groups[0].tracks) == 3


def test_an070_move_track_renames_samples_to_new_code_and_keeps_numbers_unique() -> None:
    plan = apply(make_plan(), {"op": "move_track", "track": 3, "to": "Synth"})
    assert [g.name for g in plan.groups] == ["Drums", "Synth", "Lead"]
    synth = names(plan, "Synth")
    assert synth == ["ELA_SY_Bass_01", "ELA_SY_Bass_02", "ELA_SY_Bass_03"]
    assert len(set(synth)) == 3
    assert find(plan, "ELA_SY_Bass_02").file == "ELA_SY_Bass_02.wav"
    assert plan.edits[-1]["renamed"] == {"ELA_BS_Bass_01": "ELA_SY_Bass_02", "ELA_BS_Bass_02": "ELA_SY_Bass_03"}


def test_an070_move_track_updates_merged_into() -> None:
    plan = apply(make_plan(), {"op": "merge_pieces", "track": 3, "target": "ELA_BS_Bass_01", "sources": ["ELA_BS_Bass_02"]})
    plan = apply(plan, {"op": "move_track", "track": 3, "to": "Drums"})
    assert find(plan, "ELA_DR_Bass_02").merged_into == "ELA_DR_Bass_01"


def test_an070_move_track_between_groups_with_same_code_does_not_rename() -> None:
    plan = apply(make_plan(), {"op": "move_track", "track": 5, "to": "Synth"})
    assert names(plan, "Synth") == ["ELA_SY_Bass_01", "ELA_SY_Lead_01"]
    assert plan.edits[-1]["renamed"] == {}


def test_an070_move_track_leaves_user_edited_names_alone() -> None:
    plan = make_plan()
    plan.groups[1].tracks[0].pieces[0].name = "MyBass"
    plan.groups[1].tracks[0].pieces[0].file = "MyBass.wav"
    plan = apply(plan, {"op": "move_track", "track": 3, "to": "Drums"})
    assert "MyBass" in names(plan, "Drums")


def test_an070_empty_group_disappears_after_move() -> None:
    plan = apply(make_plan(), {"op": "move_track", "track": 3, "to": "Drums"})
    assert "Bass" not in [g.name for g in plan.groups]


def test_an070_move_to_new_group_inherits_code_and_names_are_unique() -> None:
    plan = apply(make_plan(), {"op": "move_track", "track": 2, "to": None})
    plan = apply(plan, {"op": "move_track", "track": 1, "to": None})
    new = [g for g in plan.groups if g.name.startswith("Новая группа")]
    assert [g.name for g in new] == ["Новая группа", "Новая группа 2"]
    assert all(g.code == "DR" for g in new)
    assert not any(g.name == "Drums" for g in plan.groups)


def test_an070_move_over_128_pads_is_refused() -> None:
    plan = make_plan()
    plan.groups[2].tracks[0].pieces = [piece(f"ELA_SY_P_{i:02d}", [0]) for i in range(127)]
    with pytest.raises(EditError, match="128"):
        apply(plan, {"op": "move_track", "track": 3, "to": "Synth"})


def test_an070_unknown_operation_is_refused() -> None:
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "nope"})


def test_an070_result_is_a_new_plan_and_old_one_is_untouched() -> None:
    before = make_plan()
    snapshot = to_json(before)
    apply(before, {"op": "merge_groups", "groups": ["Drums", "Bass"]})
    assert to_json(before) == snapshot


def test_plan_round_trip_with_edits_and_old_plan_without_new_fields() -> None:
    plan = apply(make_plan(), merge())
    assert from_json(to_json(plan)) == plan
    old = copy.deepcopy(json.loads(to_json(make_plan())))
    del old["edits"]
    for g in old["groups"]:
        for t in g["tracks"]:
            for p in t["pieces"]:
                del p["merged_into"]
    assert from_json(json.dumps(old)).edits == []


def test_an061_report_lists_merges_moves_and_renames() -> None:
    plan = apply(make_plan(), merge())
    plan = apply(plan, {"op": "move_track", "track": 3, "to": "Synth"})
    plan = apply(plan, {"op": "rename_group", "group": "Synth", "name": "Pads"})
    text = render(plan)
    assert "Правки пользователя" in text
    assert "ELA_DR_Kick_02 объединён в ELA_DR_Kick_01" in text
    assert "ELA_BS_Bass_01 → ELA_SY_Bass_02" in text
    assert "Synth → Pads" in text
    assert "## Pads: drum, пэдов 3" in text


def test_an061_report_counts_only_exported_pieces_as_pads() -> None:
    plan = apply(make_plan(), merge(sources=["ELA_DR_Kick_02", "ELA_DR_Kick_03"]))
    assert "## Drums: drum, пэдов 2" in render(plan)


def write_samples(plan: Plan, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for g in plan.groups:
        for t in g.tracks:
            for p in t.pieces:
                sf.write(folder / p.file, np.zeros((480, 2)), 48000, subtype="PCM_24")


def built(plan: Plan, tmp_path: Path) -> xpj.Project:
    write_samples(plan, tmp_path / "samples")
    return xpj.load(xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song"))


def sequence(project: xpj.Project, name: str) -> dict:
    return next(s["value"] for s in project.data["sequences"] if s["value"]["name"] == name)


def test_an070_build_gives_no_pad_to_merged_piece_and_plays_its_notes_on_target(tmp_path: Path) -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [
        piece("ELA_DR_Kick_01", [BAR + 100], lead=0), piece("ELA_DR_Kick_02", [200], lead=0), piece("ELA_DR_Kick_03", [2 * BAR], lead=0),
    ]
    plan = apply(plan, merge(sources=["ELA_DR_Kick_02"]))
    project = built(plan, tmp_path)
    drums = next(t for t in project.data["tracks"] if t["name"] == "Drums")
    pads = [i for i in drums["program"]["drum"]["instruments"] if i["layersv"][0]["sampleFile"]]
    assert len(pads) == 3
    intro = xpj.notes_of(sequence(project, "Intro"), "Drums")
    assert sorted(time for time, pitch in intro if pitch == 36) == [200, BAR + 100]
    assert [time for time, pitch in intro if pitch == 38] == [BAR]


def test_an070_merged_occurrence_uses_lead_of_target_not_of_source(tmp_path: Path) -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [
        piece("ELA_DR_Kick_01", [1000], lead=10), piece("ELA_DR_Kick_02", [2000], lead=900),
    ]
    plan = apply(plan, merge())
    project = built(plan, tmp_path)
    kicks = sorted(t for t, pitch in xpj.notes_of(sequence(project, "Intro"), "Drums") if pitch == 36)
    assert kicks == [990, 1990]


def test_an070_merged_piece_velocity_is_taken_from_all_occurrences(tmp_path: Path) -> None:
    plan = make_plan()
    quiet = piece("ELA_DR_Kick_01", [0])
    loud = piece("ELA_DR_Kick_02", [BAR])
    quiet.occurrences[0] = Occurrence(0, 0.5)
    plan.groups[0].tracks[0].pieces = [quiet, loud]
    plan = apply(plan, merge())
    project = built(plan, tmp_path)
    events = next(c for c in sequence(project, "Intro")["trackClipMaps"][0] if c["key"] == "Drums")["value"]["eventList"]["events"]
    velocities = sorted(e["note"]["velocity"] for e in events if e["note"]["note"] == 36)
    assert velocities[0] < velocities[1]


def test_an070_merge_groups_with_repeated_name_does_not_hang() -> None:
    plan = apply(make_plan(), {"op": "merge_groups", "groups": ["Drums", "Drums", "Bass"]})
    assert [g.name for g in plan.groups] == ["Drums", "Synth", "Lead"]
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "merge_groups", "groups": ["Drums", "Drums"]})


def test_an070_split_over_128_pads_is_refused() -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [piece(f"ELA_DR_K_{i:02d}", [0]) for i in range(100)]
    plan.groups[1].tracks[0].pieces = [piece(f"ELA_BS_B_{i:02d}", [0]) for i in range(40)]
    plan = apply(plan, {"op": "merge_pieces", "track": 1, "target": "ELA_DR_K_00", "sources": [f"ELA_DR_K_{i:02d}" for i in range(1, 30)]})
    plan = apply(plan, {"op": "merge_groups", "groups": ["Drums", "Bass"]})
    assert sum(1 for p in plan.groups[0].tracks[0].pieces if p.merged_into is None) == 71
    with pytest.raises(EditError, match="128"):
        apply(plan, {"op": "split_piece", "track": 1, "target": "ELA_DR_K_00"})


@pytest.mark.parametrize("op", [
    {"op": "merge_pieces", "track": 1, "target": "ELA_DR_Kick_01", "sources": 5},
    {"op": "merge_pieces", "track": "x", "target": "ELA_DR_Kick_01", "sources": ["ELA_DR_Kick_02"]},
    {"op": "move_track", "track": 1, "to": ["Synth"]},
    {"op": "rename_group", "group": "Synth", "name": 5},
    {"op": "merge_groups", "groups": 5},
])
def test_an070_wrong_field_types_are_edit_errors(op: dict) -> None:
    with pytest.raises(EditError):
        apply(make_plan(), op)


def test_an070_unrenamed_samples_are_in_journal_and_report() -> None:
    plan = make_plan()
    plan.groups[1].tracks[0].pieces[0].name = "MyBass"
    plan.groups[1].tracks[0].pieces[0].file = "MyBass.wav"
    plan = apply(plan, {"op": "move_track", "track": 3, "to": "Drums"})
    assert plan.edits[-1]["unrenamed"] == ["MyBass"]
    assert "MyBass: имя не по правилу, код не изменён" in render(plan)


def test_an070_set_code_changes_group_code_and_renames_samples() -> None:
    plan = apply(make_plan(), {"op": "set_code", "group": "Bass", "code": "BX"})
    group = next(g for g in plan.groups if g.name == "Bass")
    assert group.code == "BX" and group.origin == "user"
    assert names(plan, "Bass") == ["ELA_BX_Bass_01", "ELA_BX_Bass_02"]
    assert find(plan, "ELA_BX_Bass_01").file == "ELA_BX_Bass_01.wav"
    assert plan.edits[-1]["renamed"] == {"ELA_BS_Bass_01": "ELA_BX_Bass_01", "ELA_BS_Bass_02": "ELA_BX_Bass_02"}


def test_an070_set_code_keeps_merged_into_and_same_code_is_noop() -> None:
    plan = apply(make_plan(), {"op": "merge_pieces", "track": 3, "target": "ELA_BS_Bass_01", "sources": ["ELA_BS_Bass_02"]})
    plan = apply(plan, {"op": "set_code", "group": "Bass", "code": "BX"})
    assert find(plan, "ELA_BX_Bass_02").merged_into == "ELA_BX_Bass_01"
    plan = apply(plan, {"op": "set_code", "group": "Bass", "code": "BX"})
    assert plan.edits[-1]["renamed"] == {}


def test_an070_set_code_to_code_of_other_group_keeps_numbers_unique() -> None:
    plan = apply(make_plan(), {"op": "set_code", "group": "Bass", "code": "SY"})
    assert names(plan, "Bass") == ["ELA_SY_Bass_02", "ELA_SY_Bass_03"]


@pytest.mark.parametrize("code", ["", "b", "BSS", "bs", "B1", "БС", 5])
def test_an070_set_code_refuses_bad_codes(code) -> None:
    with pytest.raises(EditError):
        apply(make_plan(), {"op": "set_code", "group": "Bass", "code": code})
