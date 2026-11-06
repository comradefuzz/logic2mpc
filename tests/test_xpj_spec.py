"""S-018: сборка проекта MPC по описанию формата, без донорского проекта, и контракт экспортера."""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_spec  # noqa: E402
from logic2mpc.adapters import xpj, xpj_spec
from logic2mpc.core.plan import Occurrence, PlanPiece, to_json

from logic2mpc import app
from test_export import sample_plan, version, write_samples  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
EMPTY = ROOT / "test-projects" / "reference" / "Empty.xpj"
PADS16 = ROOT / "test-projects" / "mpc" / "spike7" / "D01 pads16.xpj"
CONTRACT = ROOT / "docs" / "contracts" / "xpj-export.md"
ADAPTERS = ROOT / "logic2mpc" / "adapters"
BOUNDARY = ("xpj.py", "xpj_spec.py", "mpcfile.py")
ROOT_KEYS = {
    "version", "key", "masterTempoEnabled", "masterTempo", "samples", "tracks", "sequences",
    "currentTrackIndex", "currentSequence", "engineMode",
}
needs_references = pytest.mark.skipif(not (EMPTY.is_file() and PADS16.is_file()), reason="нет эталонов в test-projects")


def pruned(node: dict, prefix: str) -> dict:
    return build_spec.prune(node, prefix, build_spec.registry_no())


def build(tmp_path: Path, plan=None, name: str = "Song") -> xpj.ExportResult:
    plan = plan or sample_plan()
    write_samples(plan, tmp_path / "samples")
    return xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", name)


def data_of(tmp_path: Path, plan=None) -> dict:
    return xpj.load(build(tmp_path, plan).path).data


def test_no_donor_project_in_package() -> None:
    assert not (ROOT / "logic2mpc" / "template").exists()
    assert not any(hasattr(xpj, name) for name in ("TEMPLATE", "BASE_TRACK", "note_template", "clear_pads", "rename_first_track"))


def test_root_has_only_the_ten_contract_keys(tmp_path: Path) -> None:
    assert set(data_of(tmp_path)) == ROOT_KEYS


def test_no_service_tracks_and_loss_is_reported(tmp_path: Path) -> None:
    result = build(tmp_path)
    data = xpj.load(result.path).data
    assert all(t["program"]["type"] < 7 for t in data["tracks"])
    assert any("Out, Submix, Return" in loss for loss in result.losses)


def test_pads_and_events_carry_the_required_versions(tmp_path: Path) -> None:
    data = data_of(tmp_path)
    pads = [i for t in data["tracks"] for i in t["program"]["drum"]["instruments"]]
    assert len(pads) == 128 * len(data["tracks"]) and all("version" in p for p in pads)
    events = [e for s in data["sequences"] for row in s["value"]["trackClipMaps"] for c in row for e in c["value"]["eventList"]["events"]]
    assert events and all("version" in e and "version" not in e["note"] for e in events)


def schema_paths(node: object, path: str = "data") -> set[str]:
    """Пути в записи `schema.tsv`: списки как `[]`, ключи как есть."""
    found = {path}
    if isinstance(node, dict):
        for key, value in node.items():
            found |= schema_paths(value, f"{path}.{key}")
    elif isinstance(node, list):
        for value in node:
            found |= schema_paths(value, f"{path}[]")
    return found


def test_no_field_marked_no_in_the_registry_is_written_anywhere(tmp_path: Path) -> None:
    written = schema_paths(data_of(tmp_path))
    assert not written & build_spec.registry_no(), sorted(written & build_spec.registry_no())[:5]


def test_program_sample_records_keep_their_registry_fields(tmp_path: Path) -> None:
    data = data_of(tmp_path)
    program_sample = data["tracks"][1]["program"]["samples"][0]
    assert program_sample["version"] == 1 and "version" not in data["samples"][0]
    assert program_sample["name"] == data["samples"][0]["name"]


def test_twin_track_names_after_transliteration_are_refused(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].name, plan.groups[1].name = "Бас", "Bas"
    write_samples(plan, tmp_path / "samples")
    with pytest.raises(ValueError, match="Bas"):
        xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    assert not (tmp_path / "out").exists()


def test_fields_marked_no_in_the_registry_are_not_written(tmp_path: Path) -> None:
    data = data_of(tmp_path)
    pad = data["tracks"][0]["program"]["drum"]["instruments"][0]
    assert not {"coarseTune", "fineTune", "velocityScale", "bpmLock", "loopLock"} & set(pad)
    assert "version" not in pad["layersv"][0] and "version" not in data["samples"][0]


def test_hands_is_first_and_empty_groups_follow(tmp_path: Path) -> None:
    data = data_of(tmp_path)
    assert [t["name"] for t in data["tracks"]] == ["HANDS", "Drums", "Bass"]
    hands = data["tracks"][0]["program"]
    assert hands["samples"] == [] and not any(i["layersv"][0]["sampleFile"] for i in hands["drum"]["instruments"])
    assert [i["layersv"][0]["sampleFile"] for i in data["tracks"][1]["program"]["drum"]["instruments"][:2]] == [
        "ELA_DR_Kick_01.wav", "ELA_DR_Kick_02.wav",
    ]


def test_every_track_has_a_clip_in_every_sequence(tmp_path: Path) -> None:
    data = data_of(tmp_path)
    for sequence in data["sequences"]:
        assert [c["key"] for c in sequence["value"]["trackClipMaps"][0]] == ["Bass", "Drums", "HANDS"]


def test_tempo_goes_to_project_sequences_and_sample_records(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.bpm = 97.0
    data = data_of(tmp_path, plan)
    assert float(data["masterTempo"]) == 97.0
    assert all(float(s["value"]["bpm"]) == 97.0 for s in data["sequences"])
    assert all(float(s["metadata"]["tempo"]) == 97.0 for s in data["samples"])


def test_build_is_deterministic(tmp_path: Path) -> None:
    first = build(tmp_path / "a").path.read_bytes()
    second = build(tmp_path / "b").path.read_bytes()
    assert first == second


def test_notes_past_the_section_end_are_reported(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[1].tracks[0].pieces[0] = PlanPiece("B", "B.wav", 1.0, 8 * 3840, 1.0, [Occurrence(3840)])
    result = build(tmp_path, plan)
    assert any("за концом секции" in loss and "One Shot" in loss for loss in result.losses)
    assert not any("усечена" in loss for loss in result.losses)


def test_merged_pieces_are_reported(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0].tracks[0].pieces[1].merged_into = "ELA_DR_Kick_01"
    result = build(tmp_path, plan)
    assert any("слит" in loss for loss in result.losses)


def without_seeds(pad: dict) -> dict:
    pad = copy.deepcopy(pad)
    pad.pop("randomPlaySeed", None)
    for layer in pad["layersv"]:
        layer.pop("sliceIncrementRngSeed", None)
    return pad


@needs_references
def test_spec_empty_pad_equals_reference_pad_without_registry_no_fields() -> None:
    reference = xpj.load(EMPTY).data["tracks"][0]["program"]["drum"]["instruments"][0]
    expected = pruned(reference, "data.tracks[].program.drum.instruments[]")
    assert without_seeds(xpj_spec.pad(0, None, 120.0)) == without_seeds(expected)


@needs_references
def test_spec_filled_pad_differs_from_empty_only_in_the_sample_fields() -> None:
    empty, filled = xpj_spec.pad(3, None, 120.0), xpj_spec.pad(3, ("K", "K.wav", 480), 120.0)
    changed = {k for k in filled if filled[k] != empty[k]}
    assert changed - {"tempo"} == {"layersv"}
    layer_changes = {k for k in filled["layersv"][0] if filled["layersv"][0][k] != empty["layersv"][0][k]}
    assert layer_changes == {"sampleName", "sampleFile", "sliceInfo"}
    assert filled["layersv"][0]["sliceInfo"]["End"] == 479 and filled["layersv"][1:] == empty["layersv"][1:]


@needs_references
def test_spec_track_equals_reference_track_without_registry_no_fields() -> None:
    reference = xpj.load(EMPTY).data["tracks"][0]
    expected = pruned(reference, "data.tracks[]")
    expected["program"]["drum"]["instruments"] = []
    expected["program"]["samples"] = []
    made = xpj_spec.drum_track("Drum 001", True)
    assert made["program"]["drum"]["instruments"] == []
    assert made == expected


@needs_references
def test_spec_event_and_sample_keys_follow_the_reference() -> None:
    project = xpj.load(PADS16).data
    event = next(e for s in project["sequences"] for row in s["value"]["trackClipMaps"] for c in row for e in c["value"]["eventList"]["events"] if "note" in e)
    prefix = "data.sequences[].value.trackClipMaps[][].value.eventList.events[]"
    expected = pruned(event, prefix)
    made = xpj_spec.note_event(0, 36, 1.0, 480)
    assert set(made) == set(expected) and set(made["note"]) == set(expected["note"])
    sample = pruned(project["samples"][0], "data.samples[]")
    assert set(xpj_spec.sample_entry("A", "A.wav", 120.0)) == set(sample)


@needs_references
def test_spec_files_are_reproducible_from_references(tmp_path: Path) -> None:
    out = tmp_path / "spec"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_spec.py"), "--out", str(out)], check=True, capture_output=True)
    for made in sorted(out.iterdir()):
        assert made.read_bytes() == (ROOT / "logic2mpc" / "spec" / made.name).read_bytes(), made.name


# Контракт экспортера


def plan_dict() -> dict:
    return json.loads(to_json(sample_plan()))


def test_contract_schema_accepts_a_real_plan() -> None:
    xpj.validate_plan(plan_dict())


@pytest.mark.parametrize("path", [("bpm",), ("sections", 0, "bars"), ("groups", 0, "name"), ("groups", 0, "tracks", 0, "pieces", 0, "file")])
def test_contract_rejects_a_plan_without_a_read_field(path: tuple) -> None:
    plan = plan_dict()
    node = plan
    for step in path[:-1]:
        node = node[step]
    del node[path[-1]]
    with pytest.raises(xpj.ContractError):
        xpj.validate_plan(plan)


def test_contract_rejects_wrong_type_and_other_version() -> None:
    plan = plan_dict()
    plan["bpm"] = "fast"
    with pytest.raises(xpj.ContractError):
        xpj.validate_plan(plan)
    plan = plan_dict()
    plan["version"] = 99
    with pytest.raises(xpj.ContractError, match="version"):
        xpj.validate_plan(plan)


def test_invalid_plan_writes_nothing(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.bpm = "fast"  # type: ignore[assignment]
    write_samples(plan, tmp_path / "samples")
    with pytest.raises(xpj.ContractError):
        xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song")
    assert not (tmp_path / "out").exists()


def test_fields_outside_the_contract_do_not_change_the_project(tmp_path: Path) -> None:
    base = build(tmp_path / "a").path.read_bytes()
    plan = sample_plan()
    plan.song, plan.decisiveness, plan.notes_extended = "OTHER", 0.1, 5
    for group in plan.groups:
        group.code, group.origin = "ZZ", "llm"
        for track in group.tracks:
            track.rule, track.confidence, track.origin, track.remark = "X", 0.1, "llm", "заметка"
            for item in track.pieces:
                item.confidence, item.origin, item.note, item.bar = 0.2, "user", "заметка", 7.0
    assert build(tmp_path / "b", plan).path.read_bytes() == base


def imports_from_core(file: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse((ADAPTERS / file).read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 2 and node.module and node.module.startswith("core"):
            found.setdefault(node.module, set()).update(a.name for a in node.names)
    return found


def test_exporter_imports_from_core_match_the_contract_document() -> None:
    actual: dict[str, set[str]] = {}
    for file in BOUNDARY:
        for module, names in imports_from_core(file).items():
            actual.setdefault(module, set()).update(names)
    text = CONTRACT.read_text(encoding="utf-8")
    section = text.split("## Импорты из ядра", 1)[1]
    documented = {
        m.group(1): {n.strip() for n in m.group(2).split(",")}
        for m in re.finditer(r"^- `(core\.\w+)`: (.+)$", section, re.M)
    }
    assert actual == documented


def test_exporter_does_not_import_analysis_ui_or_cache() -> None:
    forbidden = ("analysis", "signal", "web", "app", "logic", "cycle", "windows", "edit", "report", "overview")
    for file in BOUNDARY:
        for module in imports_from_core(file):
            assert module.split(".")[1] not in forbidden, f"{file}: {module}"
        text = (ADAPTERS / file).read_text(encoding="utf-8")
        assert "from ..app" not in text and "from . import web" not in text and "adapters.web" not in text


def test_plan_version_in_the_schema_equals_the_code_constant() -> None:
    from logic2mpc.core.plan import PLAN_VERSION

    schema = json.loads((ROOT / "logic2mpc" / "spec" / "export-plan.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["version"]["const"] == PLAN_VERSION


def test_app_build_result_carries_the_losses(version: Path, tmp_path: Path) -> None:
    app.confirm(version)
    result = app.build_result(version, tmp_path / "out", "Song")
    assert result.path.is_file() and any("Submix" in loss for loss in result.losses)
    assert app.build(version, tmp_path / "out2", "Song").name == "Song.xpj"


ELATED_PLAN = ROOT / "test-projects" / "exports" / "elated" / "plan" / "v11" / "plan.json"


@pytest.mark.skipif(not ELATED_PLAN.is_file(), reason="нет плана Elated в test-projects")
def test_contract_schema_accepts_the_real_elated_plan() -> None:
    xpj.validate_plan(json.loads(ELATED_PLAN.read_text(encoding="utf-8")))


# S-017: режим пэда по длине образца и концу секции (AN-068)

BAR = 3840


def modes(tmp_path: Path, plan, group: int = 0, **options: object) -> list[int]:
    write_samples(plan, tmp_path / "samples")
    path = xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song", **options).path
    track = xpj.load(path).data["tracks"][group]["program"]["drum"]["instruments"]
    return [pad["triggerMode"] for pad in track[:3]]


def plan_with(pieces: list[PlanPiece]):
    plan = sample_plan()
    plan.groups[0].tracks[0].pieces = pieces
    return plan


def one(name: str, ticks: int, *occurrences: Occurrence) -> PlanPiece:
    return PlanPiece(name, f"{name}.wav", 1.0, ticks, 1.0, list(occurrences) or [Occurrence(0)])


def test_an068_long_piece_inside_its_section_is_note_on(tmp_path: Path) -> None:
    plan = plan_with([one("A", BAR, Occurrence(0), Occurrence(BAR))])  # секция 2 такта
    assert modes(tmp_path, plan, 1)[0] == 2


def test_an068_short_piece_and_piece_of_exactly_the_limit_are_one_shot(tmp_path: Path) -> None:
    plan = plan_with([one("A", BAR // 4), one("B", BAR // 2), one("C", BAR // 2 + 1)])
    assert modes(tmp_path, plan, 1) == [0, 0, 2]


def test_an068_piece_past_the_section_end_is_one_shot(tmp_path: Path) -> None:
    plan = plan_with([one("A", 2 * BAR, Occurrence(BAR))])  # от второго такта 2 тактов не помещается
    assert modes(tmp_path, plan, 1)[0] == 0


def test_an068_one_crossing_occurrence_makes_the_whole_pad_one_shot(tmp_path: Path) -> None:
    plan = plan_with([one("A", BAR, Occurrence(0), Occurrence(BAR + BAR // 2))])
    assert modes(tmp_path, plan, 1)[0] == 0


def test_an068_unplayed_length_of_an_occurrence_is_used(tmp_path: Path) -> None:
    plan = plan_with([one("A", 2 * BAR, Occurrence(BAR, length=BAR))])  # длина вхождения короче, помещается
    assert modes(tmp_path, plan, 1)[0] == 2


def test_an068_merged_occurrences_are_counted(tmp_path: Path) -> None:
    main = one("A", BAR, Occurrence(0))
    twin = PlanPiece("B", "B.wav", 1.0, BAR // 4, 1.0, [Occurrence(BAR + BAR // 2)], merged_into="A")
    assert modes(tmp_path, plan_with([main, twin]), 1)[0] == 0


def test_an068_threshold_is_a_parameter(tmp_path: Path) -> None:
    piece = one("A", 3 * BAR // 4, Occurrence(0))
    assert modes(tmp_path / "a", plan_with([piece]), 1, note_on_from="1/4")[0] == 2
    assert modes(tmp_path / "b", plan_with([piece]), 1, note_on_from="1/1")[0] == 0
    assert modes(tmp_path / "c", plan_with([piece]), 1)[0] == 2  # по умолчанию 2/4


@pytest.mark.parametrize("value", ["0", "-1/4", "abc", "1/0"])
def test_an068_invalid_threshold_is_refused_before_writing(tmp_path: Path, value: str) -> None:
    plan = plan_with([one("A", BAR)])
    write_samples(plan, tmp_path / "samples")
    with pytest.raises(ValueError):
        xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song", note_on_from=value)
    assert not (tmp_path / "out").exists()


def test_an068_note_on_pad_notes_are_not_truncated(tmp_path: Path) -> None:
    plan = plan_with([one("A", BAR, Occurrence(BAR))])
    write_samples(plan, tmp_path / "samples")
    data = xpj.load(xpj.export_project(plan, tmp_path / "samples", tmp_path / "out", "Song").path).data
    events = [e for s in data["sequences"] for c in s["value"]["trackClipMaps"][0] if c["key"] == "Drums" for e in c["value"]["eventList"]["events"]]
    assert events and all(e["note"]["length"] == BAR for e in events)


def test_an068_app_passes_the_threshold(version: Path, tmp_path: Path) -> None:
    app.confirm(version)
    strict = app.build_result(version, tmp_path / "a", "Song", note_on_from="4/1").path
    loose = app.build_result(version, tmp_path / "b", "Song", note_on_from="1/8").path
    one_shot = [p["triggerMode"] for p in xpj.load(strict).data["tracks"][1]["program"]["drum"]["instruments"][:2]]
    note_on = [p["triggerMode"] for p in xpj.load(loose).data["tracks"][1]["program"]["drum"]["instruments"][:2]]
    assert one_shot == [0, 0] and 2 in note_on
