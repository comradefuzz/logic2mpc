"""Кейсы раунда 2 спайка 9 на синтетическом проекте."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mpc_build"))
import cases  # noqa: E402
import cases2  # noqa: E402


def synthetic() -> dict[str, Any]:
    layer = {k: 0 for k in cases2.LAYER_REST} | {"version": 5, "sampleFile": "k.wav", "volume": {"law": 1}}
    pad = {k: 0 for k in cases2.PAD_TUNE + cases2.PAD_ROUTE + cases2.PAD_FLAGS} | {"version": 29, "layersv": [layer], "triggerMode": 0}
    note = {k: 0 for k in cases2.NOTE_REST + cases2.MODIFIERS} | {"version": 1, "note": 36}
    event = {"version": 2, "time": 0, "type": 3, "selected": False, "note": note}
    clip = {"key": "Drum 001", "value": {"name": "Drum 001", "eventList": {"events": [event]}}}
    program = {"type": 0, "drum": {"instruments": [pad, copy.deepcopy(pad)]}}
    return {
        "tracks": [{"name": "Drum 001", "program": program}],
        "sequences": [{"key": 0, "value": {"trackClipMaps": [[clip]]}}],
    }


def by_id(case_id: str) -> cases.Case:
    return next(c for c in cases2.build_cases() if c.id == case_id)


def mutated(case_id: str) -> dict[str, Any]:
    data = synthetic()
    by_id(case_id).mutate(data)
    return data


def test_ids_are_unique_and_limited() -> None:
    ids = [c.id for c in cases2.build_cases()]
    assert len(ids) == len(set(ids)) and len(ids) <= cases2.MAX_CASES


def test_every_case_changes_only_declared_paths() -> None:
    for case in cases2.build_cases():
        before = synthetic()
        after = copy.deepcopy(before)
        case.mutate(after)
        changed = cases.changed_paths(before, after)
        assert changed, f"{case.id}: ничего не изменилось"
        assert all(any(p.startswith(t) for t in case.touches) for p in changed), case.id


def test_pad_groups_are_disjoint_and_cover_pad_consts() -> None:
    groups = [set(cases2.PAD_TUNE), set(cases2.PAD_ROUTE), set(cases2.PAD_FLAGS)]
    assert sum(len(g) for g in groups) == len(set().union(*groups))
    pad = mutated("B05")["tracks"][0]["program"]["drum"]["instruments"][0]
    assert pad["version"] == 29 and not set().union(*groups) & set(pad)


def test_version_cases_drop_only_version() -> None:
    pad = mutated("B01")["tracks"][0]["program"]["drum"]["instruments"][0]
    assert "version" not in pad and "coarseTune" in pad
    assert "version" not in mutated("B06")["tracks"][0]["program"]["drum"]["instruments"][0]["layersv"][0]
    layer = mutated("B07")["tracks"][0]["program"]["drum"]["instruments"][0]["layersv"][0]
    assert layer["version"] == 5 and layer["sampleFile"] == "k.wav" and "pan" not in layer


def test_event_cases() -> None:
    event = lambda cid: mutated(cid)["sequences"][0]["value"]["trackClipMaps"][0][0]["value"]["eventList"]["events"][0]  # noqa: E731
    assert "version" not in event("E01") and "selected" in event("E01")
    assert "selected" not in event("E02") and "version" in event("E02")
    assert "version" not in event("E03")["note"] and event("E03")["version"] == 2
    assert not any(k.startswith("modifier") for k in event("E04")["note"]) and "probability" in event("E04")["note"]
    assert "ratchet" not in event("E05")["note"] and "modifierValue0" in event("E05")["note"]


def test_checklist_lists_every_case() -> None:
    items = cases2.build_cases()
    text = cases2.checklist(items)
    assert all(f"`{c.id} {c.slug}`" in text for c in items)
    assert text.count("| `") == len(items)
