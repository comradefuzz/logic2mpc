"""План, секции, подтверждение, отчёт и сборка проекта на синтетике."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import soundfile as sf

from logic2mpc import app
from logic2mpc.adapters import logic, logic_source, xpj
from logic2mpc.app import ConfirmationError, build, confirm
from logic2mpc.core.model import BAR, AudioRegion, Track
from logic2mpc.core.names import clean_name, sample_name
from logic2mpc.core.plan import Group, Occurrence, Plan, PlanPiece, PlanTrack, from_json, plan_hash, to_json
from logic2mpc.core.report import render
from logic2mpc.core.sections import Section, crossings, place, sections_from_markers


def piece(file: str, ticks: list[int], length: int = BAR, export: bool = True) -> PlanPiece:
    return PlanPiece(
        name=file, file=f"{file}.wav", bar=1.0, ticks=length, confidence=1.0,
        occurrences=[Occurrence(t, 1.0) for t in ticks], export=export,
    )


def sample_plan(export_second: bool = True) -> Plan:
    tracks = [PlanTrack(row=1, name="Kick", rule="AN-010", confidence=1.0, pieces=[
        piece("ELA_DR_Kick_01", [0, 2 * BAR]),
        piece("ELA_DR_Kick_02", [BAR, 3 * BAR], export=export_second),
    ])]
    bass = [PlanTrack(row=2, name="Bass", rule="AN-021", confidence=1.0, pieces=[piece("ELA_BS_Bass_01", [0], 2 * BAR)])]
    return Plan(
        song="ELA", bpm=120.0, sr=48000, decisiveness=0.775,
        sections=[Section("Intro", 0, 2), Section("Main A", 2 * BAR, 2)],
        groups=[Group("Drums", "DR", "drum", tracks), Group("Bass", "BS", "drum", bass)],
    )


def write_samples(plan: Plan, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for group in plan.groups:
        for track in group.tracks:
            for item in track.pieces:
                sf.write(folder / item.file, np.zeros((480, 2)), 48000, subtype="PCM_24")


@pytest.fixture
def version(tmp_path: Path) -> Path:
    folder = tmp_path / "v1"
    plan = sample_plan()
    write_samples(plan, folder / "samples")
    (folder / "plan.json").write_text(to_json(plan), encoding="utf-8")
    return folder


@pytest.mark.smoke
def test_plan_round_trip_keeps_everything() -> None:
    plan = sample_plan()
    assert from_json(to_json(plan)) == plan


def test_plan_every_decision_has_origin_and_confidence() -> None:
    data = json.loads(to_json(sample_plan()))
    item = data["groups"][0]["tracks"][0]["pieces"][0]
    assert item["origin"] == "rule"
    assert item["confidence"] == 1.0
    assert item["export"] is True


def test_an063_sections_from_markers() -> None:
    markers = [(0, "Intro"), (8 * BAR, "Intro B"), (16 * BAR, "Main A")]
    sections = sections_from_markers(markers, 20 * BAR)
    assert [(s.name, s.start, s.bars) for s in sections] == [("Intro", 0, 8), ("Intro B", 8 * BAR, 8), ("Main A", 16 * BAR, 4)]


def test_an063_without_markers_one_section() -> None:
    assert [(s.start, s.bars) for s in sections_from_markers([], 7 * BAR + 1)] == [(0, 8)]


def test_an063_material_before_first_marker_gets_section() -> None:
    sections = sections_from_markers([(4 * BAR, "Main")], 8 * BAR)
    assert [(s.start, s.bars) for s in sections] == [(0, 4), (4 * BAR, 4)]


def test_an063_notes_are_placed_relative_to_section() -> None:
    sections = [Section("A", 0, 2), Section("B", 2 * BAR, 2)]
    assert place(3 * BAR + 10, sections) == (1, BAR + 10)
    assert place(0, sections) == (0, 0)


def test_an063_crossing_is_reported_once() -> None:
    sections = [Section("A", 0, 2), Section("B", 2 * BAR, 2)]
    assert crossings([0, BAR, 2 * BAR], 2 * BAR, sections) == [BAR]


@pytest.mark.smoke
def test_build_refuses_without_confirm(version: Path) -> None:
    with pytest.raises(ConfirmationError):
        build(version, version.parent / "out", "ELA")


def test_build_refuses_after_plan_change(version: Path) -> None:
    confirm(version)
    path = version / "plan.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"Intro"', '"Intro 2"'), encoding="utf-8")
    with pytest.raises(ConfirmationError):
        build(version, version.parent / "out", "ELA")


@pytest.mark.smoke
def test_build_after_confirm_writes_project(version: Path) -> None:
    confirm(version)
    target = build(version, version.parent / "out", "ELA")
    assert target.name == "ELA.xpj"
    folder = target.parent / "ELA_[ProjectData]"
    assert folder.is_dir()
    assert (folder / "ELA_DR_Kick_01.wav").is_file()


def test_confirm_stores_hash(version: Path) -> None:
    confirm(version)
    stored = json.loads((version / "confirmed.json").read_text(encoding="utf-8"))
    assert stored["plan_sha256"] == plan_hash((version / "plan.json").read_text(encoding="utf-8"))


def built(plan: Plan, tmp_path: Path) -> xpj.Project:
    write_samples(plan, tmp_path / "samples")
    target = xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    return xpj.load(target)


def user_tracks(project: xpj.Project) -> list[str]:
    return [t["name"] for t in project.data["tracks"] if t["program"]["type"] < 7]


def test_build_first_track_is_the_first_group(tmp_path: Path) -> None:
    project = built(sample_plan(), tmp_path)
    assert user_tracks(project) == ["Drums", "Bass"]
    assert project.data["tracks"][0]["program"]["samples"]


def test_build_arms_only_current_track(tmp_path: Path) -> None:
    data = built(sample_plan(), tmp_path).data
    armed = [i for i, t in enumerate(data["tracks"]) if t["recordArm"]]
    assert armed == [data["currentTrackIndex"]]


def test_build_name_of_file_and_folder_match(tmp_path: Path) -> None:
    plan = sample_plan()
    write_samples(plan, tmp_path / "samples")
    target = xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Песня")
    assert target.name == "Pesnya.xpj"
    assert (target.parent / "Pesnya_[ProjectData]").is_dir()


def test_build_sequences_follow_sections(tmp_path: Path) -> None:
    project = built(sample_plan(), tmp_path)
    values = sorted((s["value"] for s in project.data["sequences"]), key=lambda v: v["name"])
    assert [(v["name"], v["lengthBars"], v["lengthPulses"]) for v in values] == [
        ("Intro", 2, 2 * BAR), ("Main A", 2, 2 * BAR),
    ]
    assert {s["key"] for s in project.data["sequences"]} == {0, 1}


def test_build_notes_are_in_expected_ticks(tmp_path: Path) -> None:
    project = built(sample_plan(), tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    notes = xpj.notes_of(by_name["Intro"]["value"], "Drums")
    assert notes == [(0, 36), (BAR, 37)]
    notes = xpj.notes_of(by_name["Main A"]["value"], "Drums")
    assert notes == [(0, 36), (BAR, 37)]


def test_build_note_length_does_not_pass_section_end(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[1].tracks[0].pieces[0] = piece("ELA_BS_Bass_01", [BAR], 2 * BAR)
    project = built(plan, tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    event = by_name["Intro"]["value"]["trackClipMaps"][0]
    bass = next(c for c in event if c["key"] == "Bass")["value"]["eventList"]["events"][0]
    assert bass["note"]["length"] == BAR


def test_an010_an063_hit_on_section_start_stays_in_its_section(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks[0].pieces = [
        PlanPiece("K", "K.wav", 1.0, 100, 1.0, [Occurrence(0), Occurrence(2 * BAR)], lead=38),
    ]
    project = built(plan, tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    assert xpj.notes_of(by_name["Intro"]["value"], "Drums") == [(0, 36)]
    assert xpj.notes_of(by_name["Main A"]["value"], "Drums") == [(0, 36)]
    assert "через границу" not in render(plan)


def test_an063_crossing_note_is_only_in_its_section(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[1].tracks[0].pieces = [piece("B", [BAR], 2 * BAR)]
    project = built(plan, tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    assert xpj.notes_of(by_name["Intro"]["value"], "Bass") == [(BAR, 36)]
    assert xpj.notes_of(by_name["Main A"]["value"], "Bass") == []


def test_build_export_false_is_left_out(tmp_path: Path) -> None:
    project = built(sample_plan(export_second=False), tmp_path)
    assert "ELA_DR_Kick_02" not in {s["name"] for s in project.data["samples"]}
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    assert xpj.notes_of(by_name["Intro"]["value"], "Drums") == [(0, 36)]
    assert not (tmp_path / "out" / "Song_[ProjectData]" / "ELA_DR_Kick_02.wav").exists()


def test_build_missing_sample_writes_nothing(tmp_path: Path) -> None:
    plan = sample_plan()
    write_samples(plan, tmp_path / "samples")
    (tmp_path / "samples" / "ELA_BS_Bass_01.wav").unlink()
    with pytest.raises(FileNotFoundError, match="ELA_BS_Bass_01"):
        xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    assert not (tmp_path / "out").exists()


def test_build_more_than_128_pads_is_error(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks[0].pieces = [piece(f"S{i}", [0]) for i in range(129)]
    write_samples(plan, tmp_path / "samples")
    with pytest.raises(ValueError, match="128"):
        xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")


def test_build_velocity_comes_from_gain(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks[0].pieces = [
        PlanPiece("K", "K.wav", 1.0, BAR, 1.0, [Occurrence(0, 2.0), Occurrence(BAR, 1.0)]),
    ]
    project = built(plan, tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    clips = by_name["Intro"]["value"]["trackClipMaps"][0]
    events = next(c for c in clips if c["key"] == "Drums")["value"]["eventList"]["events"]
    assert [float(e["note"]["velocity"]) for e in events] == [1.0, 0.5]


@pytest.mark.smoke
def test_build_file_survives_reread_with_same_numbers(tmp_path: Path) -> None:
    plan = sample_plan()
    write_samples(plan, tmp_path / "samples")
    target = xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    raw = xpj.gzip.decompress(target.read_bytes())
    assert xpj.render(xpj.parse(raw)) == raw


def test_an050_an063_report_lists_open_edges_and_crossings() -> None:
    plan = sample_plan()
    item = plan.groups[1].tracks[0].pieces[0]
    item.start_open, item.end_open = False, True
    item.occurrences = [Occurrence(BAR, 1.0)]
    text = render(plan)
    assert "ELA_BS_Bass_01: конец не в нуле" in text
    assert "через границу секции: такт 2" in text


def test_report_lists_muted_regions_and_losses() -> None:
    plan = sample_plan()
    track = plan.groups[0].tracks[0]
    track.muted_bars, track.lost_bars = [33.0], [53.0]
    text = render(plan)
    assert "Выключенные регионы: такты 33" in text
    assert "Потеряны такты: 53" in text


def test_report_lists_replaced_bars_and_remark() -> None:
    plan = sample_plan()
    track = plan.groups[0].tracks[0]
    track.replaced_bars, track.remark = [25.0], "в экспорте нет звука"
    text = render(plan)
    assert "Заменены образцом такты: 25" in text
    assert "Внимание: в экспорте нет звука" in text


def test_build_short_pass_gets_short_note(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[1].tracks[0].pieces = [
        PlanPiece("B", "B.wav", 1.0, 2 * BAR, 1.0, [Occurrence(0, 1.0, BAR)]),
    ]
    project = built(plan, tmp_path)
    by_name = {s["value"]["name"]: s for s in project.data["sequences"]}
    clips = by_name["Intro"]["value"]["trackClipMaps"][0]
    assert next(c for c in clips if c["key"] == "Bass")["value"]["eventList"]["events"][0]["note"]["length"] == BAR


def test_clean_name_removes_pack_tempo_key_and_service_words() -> None:
    assert clean_name("DS_LENNO_drum_kick_nerve") == "KickNerve"
    assert clean_name("JAFUNK_120_shaker_laid_back") == "ShakerLaidBack"
    assert clean_name("ah_vox_115_emeli_E") == "AhVoxEmeli"
    assert clean_name("SY - Fire Glow") == "FireGlow"
    assert clean_name("PD Gated Pad [AS]") == "GatedPad"
    assert clean_name("Бас Оливер") == "BasOliver"


def test_sample_name_uses_group_and_number_when_name_is_empty() -> None:
    assert sample_name("PYR", "BS", "Bass", 1) == "PYR_BS_Bass_01"
    assert sample_name("ELA", "DR", "", 2, row=24) == "ELA_DR_DrTrk24_02"
    assert sample_name("PYR", "BS", "Bass", 1, note="C2") == "PYR_BS_Bass_01_C2"


def test_an003_fully_muted_track_is_in_report() -> None:
    plan = sample_plan()
    plan.muted_tracks = ["Fill Long"]
    assert "в проект не вошли: Fill Long" in render(plan)


def song(tracks: list[Track]) -> logic.Song:
    return logic.Song(120.0, 48000, tracks, [(0, "Intro")], 0, 0)


@pytest.fixture
def analyzed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def run(tracks: list[Track], files: dict[int, np.ndarray]) -> Path:
        monkeypatch.setattr(logic_source, "read_project", lambda _: song(tracks))
        export = tmp_path / "export"
        export.mkdir(exist_ok=True)
        for number, audio in files.items():
            sf.write(export / f"{number:02d}_T.wav", audio, 48000, subtype="PCM_24")
        groups = tmp_path / "groups.json"
        groups.write_text(json.dumps({"song": "ELA", "groups": {"Bass": {"code": "BS"}}}), encoding="utf-8")
        return app.analyze(Path("p.logicx"), export, groups, tmp_path / "plan")

    return run


def tone(frames: int = 96000) -> np.ndarray:
    wave = 0.5 * np.sin(np.arange(frames) * 0.05)
    return np.stack([wave, wave], axis=1)


def test_an071_track_outside_stack_goes_to_other_group(analyzed) -> None:
    folder = analyzed([Track(0, "Bass", None, [], [AudioRegion(0)])], {1: tone()})
    plan = from_json((folder / "plan.json").read_text(encoding="utf-8"))
    assert [(g.name, g.code) for g in plan.groups] == [("Прочее", "OT")]
    assert plan.groups[0].tracks[0].pieces[0].name == "ELA_OT_Bass_01"


def test_analyze_unknown_group_is_error(analyzed) -> None:
    with pytest.raises(ValueError, match="нет группы в настройках: Other"):
        analyzed([Track(0, "T", "Other", [], [AudioRegion(0)])], {1: tone()})


def test_analyze_missing_export_is_error(analyzed) -> None:
    with pytest.raises(FileNotFoundError, match="T"):
        analyzed([Track(0, "T", "Bass", [], [AudioRegion(0)])], {})


def test_an003_analyze_records_fully_muted_track_with_row(analyzed) -> None:
    folder = analyzed(
        [Track(0, "T", "Bass", [], [AudioRegion(0)]), Track(1, "Off", "Bass", [], [AudioRegion(0, muted=True)])],
        {1: tone()},
    )
    assert from_json((folder / "plan.json").read_text(encoding="utf-8")).muted_tracks == ["Off (строка 2)"]


def test_an050_sample_is_exact_copy_of_export(analyzed) -> None:
    audio = tone()
    folder = analyzed([Track(0, "T", "Bass", [], [AudioRegion(0)])], {1: audio})
    sample, _ = sf.read(folder / "samples" / "ELA_BS_T_01.wav", always_2d=True)
    assert np.allclose(sample, audio, atol=1e-6)


def test_an062_new_run_is_new_version(analyzed) -> None:
    tracks = [Track(0, "T", "Bass", [], [AudioRegion(0)])]
    assert analyzed(tracks, {1: tone()}).name == "v1"
    assert analyzed(tracks, {1: tone()}).name == "v2"


# S-021: экспорт без пустого трека HANDS


def built_data(tmp_path: Path, plan: Plan | None = None) -> dict:
    plan = plan or sample_plan()
    write_samples(plan, tmp_path / "samples")
    return xpj.load(xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")).data


@pytest.mark.smoke
def test_first_track_is_the_first_group_and_no_hands(tmp_path: Path) -> None:
    data = built_data(tmp_path)
    assert [t["name"] for t in data["tracks"] if t["program"]["type"] < 7] == ["Drums", "Bass"]
    first = data["tracks"][0]["program"]["drum"]["instruments"]
    assert [i["layersv"][0]["sampleFile"] for i in first[:2]] == ["ELA_DR_Kick_01.wav", "ELA_DR_Kick_02.wav"]


def test_record_arm_only_on_the_first_track_which_is_current(tmp_path: Path) -> None:
    data = built_data(tmp_path)
    assert data["currentTrackIndex"] == 0
    assert [t["recordArm"] for t in data["tracks"] if t["program"]["type"] < 7] == [True, False]


def test_sequences_have_clips_only_for_group_tracks(tmp_path: Path) -> None:
    for sequence in built_data(tmp_path)["sequences"]:
        assert [c["key"] for c in sequence["value"]["trackClipMaps"][0]] == ["Bass", "Drums"]


def test_plan_without_groups_is_refused_before_writing(tmp_path: Path) -> None:
    plan = dataclasses.replace(sample_plan(), groups=[])
    with pytest.raises(ValueError):
        xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    assert not (tmp_path / "out").exists()


def test_schema_rejects_empty_groups() -> None:
    schema = json.loads(xpj.SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["groups"]["minItems"] == 1
    plan = json.loads(json.dumps(dataclasses.asdict(sample_plan())))
    plan["groups"] = []
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(plan))
