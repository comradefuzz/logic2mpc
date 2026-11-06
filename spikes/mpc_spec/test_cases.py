"""Кейсы спайка 9 на синтетическом проекте."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mpc_build"))
import cases  # noqa: E402
import patch  # noqa: E402

HEADER = b"ACVS\n3.10.0.49\nSerialisableProjectData\njson\nLinux\n"

CONSTS = {
    "tracks[].cvPort", "tracks[].program.midi.channel", "tracks[].program.drum.instruments[].version",
    "sequences[].value.trackClipMaps[][].value.loop", "sequences[].value.trackClipMaps[][].value.eventList.events[].type",
    "samples[].version", "sequences[].value.version",
}


def pad(sample: str = "") -> dict[str, Any]:
    return {
        "layersv": [{"sampleFile": sample}], "triggerMode": 0, "polyphony": 1, "monophonic": True,
        "whichMuteGroup": 0, "warpEnable": False, "version": 29,
    }


def track(name: str, kind: int, instruments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    program: dict[str, Any] = {"type": kind, "name": name, "mixable": {"mute": False}}
    if kind == 0:
        program["drum"] = {"instruments": instruments or []}
    if kind == 4:
        program["midi"] = {"channel": 0, "extra": 1}
    return {"name": name, "colour": 5, "recordArm": kind == 0, "cvPort": 0, "mute": False, "program": program}


def synthetic() -> dict[str, Any]:
    clip = {"key": "Drum 001", "value": {"name": "Drum 001", "loop": True, "eventList": {"events": [
        {"time": 0, "type": 3, "note": {"note": 36}},
    ]}}}
    return {
        "version": 30, "key": 1, "mixer": {"a": 1}, "scene": {"b": 1}, "songs": [{"name": "(unnamed)"}],
        "assignableXFaderAssignments": {}, "qlinkMode": 0, "rowLaunchSnapshotAssignments": {},
        "midiLearnSettings": {}, "parameterSnapshotterData": {}, "guiNormalTracksMemento": {},
        "tuiMainModeLayout": {}, "mpcClipMatrixView": {}, "horizontalClipMatrixView": {}, "sharedClipMatrixData": {},
        "masterTempo": 120.0, "masterTempoEnabled": True, "engineMode": 1, "currentTrackIndex": 0, "currentSequence": 0,
        "samples": [{"name": "k", "path": "k.wav", "version": 1}],
        "tracks": [
            track("Drum 001", 0, [pad("k.wav"), pad("s.wav"), pad()]), track("Midi 001", 4),
            track("Submix 1", 8), track("Return 1", 7), track("Out 1/2", 9),
        ],
        "sequences": [{"key": 0, "value": {"name": "Seq", "version": 2, "trackClipMaps": [[clip]]}}],
    }


def case_list() -> list[cases.Case]:
    return cases.build_cases(CONSTS)


def by_id(case_id: str) -> cases.Case:
    return next(c for c in case_list() if c.id == case_id)


def test_ids_are_unique_and_limited() -> None:
    ids = [c.id for c in case_list()]
    assert len(ids) == len(set(ids)) and len(ids) <= 25


def test_every_case_is_described() -> None:
    for case in case_list():
        assert case.slug and case.base and case.text and case.touches, case.id
        assert case.base.endswith(".xpj"), case.id


def test_every_case_changes_only_declared_paths() -> None:
    for case in case_list():
        before = synthetic()
        after = copy.deepcopy(before)
        case.mutate(after)
        changed = cases.changed_paths(before, after)
        assert changed, f"{case.id}: ничего не изменилось"
        stray = {p for p in changed if not any(p.startswith(t) for t in case.touches)}
        assert not stray, f"{case.id}: вне заявленного {sorted(stray)[:3]}"


def test_service_cases_drop_exact_types() -> None:
    kinds = lambda case: sorted(t["program"]["type"] for t in mutated(case)["tracks"])  # noqa: E731
    assert kinds(by_id("Z01")) == [0, 4]
    assert kinds(by_id("Z02")) == [0, 4, 7, 8]
    assert kinds(by_id("Z03")) == [0, 4, 9]


def mutated(case: cases.Case) -> dict[str, Any]:
    data = synthetic()
    case.mutate(data)
    return data


def test_root_cases() -> None:
    assert "mixer" not in mutated(by_id("R01")) and "scene" not in mutated(by_id("R02"))
    assert "songs" not in mutated(by_id("R03"))
    r4 = mutated(by_id("R04"))
    assert not any(k.startswith(("assignable", "qlink", "rowLaunch", "midiLearn", "parameterSnapshotter")) for k in r4)
    r5 = mutated(by_id("R05"))
    assert not any(k.startswith(("gui", "tui")) or k in ("mpcClipMatrixView", "horizontalClipMatrixView", "sharedClipMatrixData") for k in r5)
    r6 = mutated(by_id("R06"))
    assert set(r6) == set(cases.ROOT_KEEP) and all(r6[k] == synthetic()[k] for k in cases.ROOT_KEEP)


def test_pad_cases_touch_filled_pads_only() -> None:
    pads = lambda case: mutated(case)["tracks"][0]["program"]["drum"]["instruments"]  # noqa: E731
    assert [p["triggerMode"] for p in pads(by_id("P01"))] == [2, 2, 0]
    assert [(p["monophonic"], p["polyphony"]) for p in pads(by_id("P02"))] == [(False, 1), (False, 1), (True, 1)]
    assert [(p["monophonic"], p["polyphony"]) for p in pads(by_id("P03"))] == [(False, 4), (False, 4), (True, 1)]
    assert [p["warpEnable"] for p in pads(by_id("P05"))] == [True, True, False]
    assert [p["whichMuteGroup"] for p in pads(by_id("P06"))] == [1, 1, 0]


def test_trigger_mode_flips_both_ways() -> None:
    data = synthetic()
    for inst in data["tracks"][0]["program"]["drum"]["instruments"]:
        inst["triggerMode"] = 2
    by_id("P01").mutate(data)
    assert [i["triggerMode"] for i in data["tracks"][0]["program"]["drum"]["instruments"]] == [0, 0, 2]


def test_minimal_cases_drop_only_const_keys() -> None:
    drum = mutated(by_id("T01"))["tracks"][0]
    assert "cvPort" not in drum and "colour" in drum and "program" in drum
    assert "version" not in mutated(by_id("P04"))["tracks"][0]["program"]["drum"]["instruments"][0]
    assert "channel" not in mutated(by_id("M01"))["tracks"][1]["program"]["midi"]
    assert "loop" not in mutated(by_id("Q01"))["sequences"][0]["value"]["trackClipMaps"][0][0]["value"]
    assert "type" not in mutated(by_id("Q02"))["sequences"][0]["value"]["trackClipMaps"][0][0]["value"]["eventList"]["events"][0]
    assert "version" not in mutated(by_id("Q03"))["samples"][0]
    assert "version" not in mutated(by_id("Q04"))["sequences"][0]["value"]


def test_track_cases() -> None:
    assert "colour" not in mutated(by_id("T02"))["tracks"][0]
    assert "mixable" not in mutated(by_id("T03"))["tracks"][0]["program"]
    assert not any(t["recordArm"] for t in mutated(by_id("T04"))["tracks"])


def test_changed_paths_names_adds_removals_and_values() -> None:
    before = {"a": 1, "b": {"c": [1, 2]}, "d": 4}
    after = {"a": 2, "b": {"c": [1, 3, 5]}, "e": 7}
    assert cases.changed_paths(before, after) == {"a", "b.c[1]", "b.c[2]", "d", "e"}


def write_base(directory: Path, name: str = "Base") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.xpj"
    path.write_bytes(patch.pack(patch.render(patch.Project(HEADER, synthetic()))))
    folder = directory / f"{name}_[ProjectData]"
    folder.mkdir()
    (folder / "k.wav").write_bytes(b"x")
    return path


def test_write_case_names_project_and_folder_alike(tmp_path: Path) -> None:
    base = write_base(tmp_path / "base")
    out = cases.write_case(by_id("R01"), base, tmp_path / "out")
    assert out.name == "R01 no-mixer.xpj"
    assert (tmp_path / "out" / "R01 no-mixer_[ProjectData]" / "k.wav").is_file()
    assert "mixer" not in patch.load(out).data and patch.load(out).data["tracks"][0]["name"] == "Drum 001"


def test_write_case_without_data_folder_makes_empty_one(tmp_path: Path) -> None:
    base = write_base(tmp_path / "base")
    (tmp_path / "base" / "Base_[ProjectData]" / "k.wav").unlink()
    (tmp_path / "base" / "Base_[ProjectData]").rmdir()
    out = cases.write_case(by_id("Z01"), base, tmp_path / "out")
    assert (out.parent / "Z01 no-service_[ProjectData]").is_dir()


def test_checklist_lists_every_case_and_only_them() -> None:
    text = cases.checklist(case_list())
    rows = [line for line in text.splitlines() if line.startswith("| `")]
    assert [r.split("`")[1] for r in rows] == [f"{c.id} {c.slug}" for c in case_list()]


def test_remove_stale_deletes_old_cases_only(tmp_path: Path) -> None:
    out = tmp_path / "out"
    keep = case_list()[0]
    for name in (f"{keep.id} {keep.slug}", "P02 mono"):
        (out / f"{name}.xpj").parent.mkdir(exist_ok=True)
        (out / f"{name}.xpj").write_bytes(b"x")
        (out / f"{name}_[ProjectData]").mkdir()
    (out / "notes.txt").write_text("мои заметки")
    gone = cases.remove_stale(out, case_list())
    assert gone == ["P02 mono.xpj", "P02 mono_[ProjectData]"]
    assert (out / f"{keep.id} {keep.slug}.xpj").is_file() and (out / "notes.txt").is_file()
