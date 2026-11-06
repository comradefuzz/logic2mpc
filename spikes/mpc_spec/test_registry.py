"""Реестр полей для экспорта на синтетической схеме."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry  # noqa: E402

SCHEMA = """# файлов 3, путей 12
# 3 × ACVS / 3.10.0.49 / SerialisableProjectData / json / Linux
data	3	dict	
data.masterTempo	3	float [95.0 .. 120.0] {120.0, 95.0}	
data.mixer	3	dict	
data.tracks	3	list	
data.tracks[]	9	dict	0,1,3,4,7
data.tracks[].name	9	str (9 значений)	
data.tracks[].cvPort	9	int [0 .. 0] {0}	
data.tracks[].recordArm	9	bool {False, True}	
data.tracks[].volume	9	float [0.69 .. 1.0] {1.0, 0.69}	
data.tracks[].pan	9	float [0.5 .. 0.5] {0.5}	
data.tracks[].program.drum.instruments[].polyphony	99	int [0 .. 4] {1, 0, 4}	0,1
data.tracks[].program.drum.instruments[].layersv	99	list	0,1
data.tracks[].program.keygroup.numKeygroups	4	int [1 .. 1] {1}	1
data.tracks[].program.plugin.state	2	str (2 значений)	3
data.tracks[].program.midi.channel	2	int [0 .. 0] {0}	4
data.sequences[].value.name	5	str (5 значений)	
data.samples[].path	7	str (7 значений)	
data.locators.colours	3	list	
"""


def rows() -> dict[str, registry.Row]:
    return {r.path: r for r in registry.parse_schema(SCHEMA)}


def test_parse_values_and_kinds() -> None:
    found = rows()
    poly = found["data.tracks[].program.drum.instruments[].polyphony"]
    assert poly.kinds == {"int"} and poly.values == ["1", "0", "4"] and poly.programs == {0, 1}
    arm = found["data.tracks[].recordArm"]
    assert arm.kinds == {"bool"} and arm.values == ["False", "True"]
    assert found["data.tracks[].name"].values is None
    assert found["data.mixer"].kinds == {"dict"} and found["data.mixer"].values == []


def test_comment_lines_are_skipped() -> None:
    assert all(not r.path.startswith("#") for r in registry.parse_schema(SCHEMA))


def test_classes() -> None:
    found = rows()
    assert registry.classify(found["data.tracks[].cvPort"]) == "const"
    assert registry.classify(found["data.tracks[].recordArm"]) == "var"
    assert registry.classify(found["data.tracks[].name"]) == "ref"
    assert registry.classify(found["data.samples[].path"]) == "ref"
    assert registry.classify(found["data.mixer"]) == "node"
    assert registry.classify(found["data.tracks[]"]) == "node"


def test_scope_keeps_export_objects_only() -> None:
    kept = {r.path for r in registry.parse_schema(SCHEMA) if registry.in_scope(r)}
    assert "data.tracks[].cvPort" in kept
    assert "data.tracks[].program.drum.instruments[].polyphony" in kept
    assert "data.tracks[].program.midi.channel" in kept
    assert "data.sequences[].value.name" in kept and "data.samples[].path" in kept
    assert "data.masterTempo" in kept and "data.mixer" in kept
    assert "data.tracks[].program.keygroup.numKeygroups" not in kept
    assert "data.tracks[].program.plugin.state" not in kept


def test_volume_and_pan_are_optional() -> None:
    table = {r["path"]: r for r in registry.build_rows(SCHEMA)}
    assert table["data.tracks[].volume"]["note"] == "optional-export"
    assert table["data.tracks[].pan"]["note"] == "optional-export"
    assert table["data.tracks[].recordArm"]["note"] == ""


def test_row_columns_start_unknown_and_empty() -> None:
    row = {r["path"]: r for r in registry.build_rows(SCHEMA)}["data.tracks[].cvPort"]
    assert list(row) == list(registry.COLUMNS)
    assert row["class"] == "const" and row["observed"] == "0"
    assert row["required"] == "unknown" and row["export_value"] == "" and row["fact"] == ""


def test_render_and_read_roundtrip_sorted() -> None:
    built = registry.build_rows(SCHEMA)
    text = registry.render(built)
    assert registry.read(text) == built
    paths = [r["path"] for r in built]
    assert paths == sorted(paths)
    assert text.splitlines()[0] == "\t".join(registry.COLUMNS)


def test_merge_keeps_filled_columns_and_adds_new_paths() -> None:
    old = registry.build_rows(SCHEMA)
    for row in old:
        if row["path"] == "data.tracks[].cvPort":
            row["required"], row["export_value"], row["fact"], row["note"] = "no", "0", "MPC-032", "ok"
    old = [r for r in old if r["path"] != "data.mixer"] + [dict(old[0], path="data.gone")]
    merged = {r["path"]: r for r in registry.merge(old, registry.build_rows(SCHEMA))}
    kept = merged["data.tracks[].cvPort"]
    assert (kept["required"], kept["export_value"], kept["fact"], kept["note"]) == ("no", "0", "MPC-032", "ok")
    assert "data.mixer" in merged and "data.gone" in merged
