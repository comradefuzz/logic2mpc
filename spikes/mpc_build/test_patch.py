"""Сборка .xpj на синтетическом проекте."""
from __future__ import annotations

import copy
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch  # noqa: E402

HEADER = "ACVS\n3.10.0.49\nSerialisableProjectData\njson\nLinux\n"
BODY = """{
"data": {
"version": 30,
"masterTempo": 120.0,
"weird": 0.36730000376701357,
"big": 9223372036854775807,
"empty": [],
"none": {},
"text": "a/b \\"q\\" Ё",
"tracks": [
{
"name": "Drum 001",
"program": {
"type": 0
}
},
{
"name": "Submix 1",
"program": {
"type": 8
}
}
],
"sequences": [
{
"key": 0,
"value": {
"name": "Sequence 01",
"bpm": 120.0,
"trackClipMaps": [
[
{
"key": "Drum 001",
"value": {
"name": "Drum 001",
"eventList": {
"events": [
{
"time": 0,
"type": 3,
"note": {
"note": 36,
"velocity": 1.0,
"length": 480
}
}
]
}
}
},
{
"key": "Submix 1",
"value": {
"name": "Submix 1",
"eventList": {
"events": []
}
}
}
]
]
}
}
]
}
}"""


def project() -> patch.Project:
    return patch.parse((HEADER + BODY).encode())


def test_round_trip_keeps_bytes() -> None:
    assert patch.render(project()).decode() == HEADER + BODY


def test_changed_value_keeps_other_floats_exact() -> None:
    item = project()
    item.data["masterTempo"] = 97.0
    text = patch.render(item).decode()
    assert '"masterTempo": 97.0,' in text
    assert '"weird": 0.36730000376701357,' in text


def test_notes_are_added_from_template() -> None:
    item = project()
    patch.set_notes(item, 0, "Drum 001", [(0, 36, 1.0, 240), (960, 37, 0.5, 240)])
    events = patch.clip(item, 0, "Drum 001")["eventList"]["events"]
    assert [e["time"] for e in events] == [0, 960]
    assert events[1]["note"]["note"] == 37
    assert events[1]["note"]["velocity"] == 0.5
    assert events[1]["note"]["length"] == 240


def test_track_goes_before_submix_and_clip_stays_sorted() -> None:
    item = project()
    track = copy.deepcopy(item.data["tracks"][0])
    patch.insert_track(item, track, "Bass")
    assert [t["name"] for t in item.data["tracks"]] == ["Drum 001", "Bass", "Submix 1"]
    assert track["program"]["name"] == "Bass"
    keys = [c["key"] for c in item.data["sequences"][0]["value"]["trackClipMaps"][0]]
    assert keys == ["Bass", "Drum 001", "Submix 1"]
    assert patch.clip(item, 0, "Bass")["name"] == "Bass"
    assert patch.clip(item, 0, "Bass")["eventList"]["events"] == []


def test_write_uses_gzip_header_of_device() -> None:
    packed = patch.pack(patch.render(project()))
    assert packed[:10].hex() == "1f8b0800000000000003"
    assert gzip.decompress(packed).decode() == HEADER + BODY
