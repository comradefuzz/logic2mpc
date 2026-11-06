"""S-012: просмотр собранного проекта MPC, чтение из .xpj."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from logic2mpc.adapters import web, xpj, xpj_view
from logic2mpc.app import Session
from logic2mpc.core.edit import apply
from logic2mpc.core.model import BAR
from logic2mpc.core.overview import summarize
from logic2mpc.core.plan import Plan, to_json

from test_edit import make_plan, merge, piece

HOST = "http://127.0.0.1:8765"


def write_samples(plan: Plan, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for g in plan.groups:
        for t in g.tracks:
            for p in t.pieces:
                sf.write(folder / p.file, np.zeros((480 + len(p.file), 2)), 48000, subtype="PCM_24")


def build(plan: Plan, tmp_path: Path, name: str = "Song") -> Path:
    write_samples(plan, tmp_path / "samples")
    return xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", name)


def test_overview_lists_tracks_with_hands_first_and_empty(tmp_path: Path) -> None:
    view = xpj_view.read_overview(build(make_plan(), tmp_path))
    assert [t["name"] for t in view["tracks"]] == ["HANDS", "Drums", "Bass", "Synth", "Lead"]
    assert [t["filled"] for t in view["tracks"]] == [0, 4, 2, 1, 1]
    assert view["tracks"][0]["pads"] == []
    assert all(t["kind"] == "drum" for t in view["tracks"])


def test_overview_pad_has_number_bank_note_and_sample(tmp_path: Path) -> None:
    view = xpj_view.read_overview(build(make_plan(), tmp_path))
    drums = next(t for t in view["tracks"] if t["name"] == "Drums")
    first, second = drums["pads"][0], drums["pads"][1]
    assert (first["pad"], first["bank"], first["number"], first["note"]) == (0, "A", 1, 36)
    assert first["sample"] == "ELA_DR_Kick_01" and first["file"] == "ELA_DR_Kick_01.wav" and first["exists"] is True
    assert (second["pad"], second["note"]) == (1, 37)


def test_overview_pad_16_is_first_pad_of_bank_b(tmp_path: Path) -> None:
    plan = make_plan()
    plan.groups[0].tracks[0].pieces = [piece(f"ELA_DR_K_{i:02d}", [0]) for i in range(20)]
    view = xpj_view.read_overview(build(plan, tmp_path))
    pad = next(t for t in view["tracks"] if t["name"] == "Drums")["pads"][16]
    assert (pad["pad"], pad["bank"], pad["number"]) == (16, "B", 1)


def test_overview_merged_away_piece_has_no_pad_and_is_not_a_sample(tmp_path: Path) -> None:
    plan = apply(make_plan(), merge())
    view = xpj_view.read_overview(build(plan, tmp_path))
    drums = next(t for t in view["tracks"] if t["name"] == "Drums")
    assert drums["filled"] == 3
    assert "ELA_DR_Kick_02.wav" not in {p["file"] for t in view["tracks"] for p in t["pads"]}
    assert view["samples"] == 7


def test_overview_sequences_follow_sections_with_bars(tmp_path: Path) -> None:
    view = xpj_view.read_overview(build(make_plan(), tmp_path))
    assert view["sequences"] == [{"name": "Intro", "bars": 2}, {"name": "Main A", "bars": 2}]


def test_overview_sizes_match_files_on_disk(tmp_path: Path) -> None:
    project = build(make_plan(), tmp_path)
    data = project.parent / "Song_[ProjectData]"
    view = xpj_view.read_overview(project)
    wavs = sum(p.stat().st_size for p in data.iterdir())
    assert view["size"] == {"project": project.stat().st_size, "samples": wavs, "total": project.stat().st_size + wavs}
    assert view["samples"] == 8 and view["missing"] == [] and view["extra"] == []


def test_overview_names_missing_and_extra_files(tmp_path: Path) -> None:
    project = build(make_plan(), tmp_path)
    data = project.parent / "Song_[ProjectData]"
    (data / "ELA_DR_Kick_01.wav").unlink()
    (data / "stray.wav").write_bytes(b"x")
    view = xpj_view.read_overview(project)
    assert view["missing"] == ["ELA_DR_Kick_01.wav"] and view["extra"] == ["stray.wav"]
    first = next(t for t in view["tracks"] if t["name"] == "Drums")["pads"][0]
    assert first["exists"] is False


def test_overview_ignores_appledouble_files_in_extra_and_size(tmp_path: Path) -> None:
    project = build(make_plan(), tmp_path)
    data = project.parent / "Song_[ProjectData]"
    before = xpj_view.read_overview(project)
    (data / "._ELA_DR_Kick_01.wav").write_bytes(b"x" * 4096)
    view = xpj_view.read_overview(project)
    assert view["extra"] == [] and view["size"] == before["size"]


def test_overview_without_data_folder_reports_everything_missing(tmp_path: Path) -> None:
    import shutil

    project = build(make_plan(), tmp_path)
    shutil.rmtree(project.parent / "Song_[ProjectData]")
    view = xpj_view.read_overview(project)
    assert len(view["missing"]) == 8 and view["size"]["samples"] == 0


def test_overview_broken_files_are_value_errors(tmp_path: Path) -> None:
    bad = tmp_path / "Bad.xpj"
    bad.write_bytes(b"not a project")
    with pytest.raises(ValueError, match="не удалось прочитать"):
        xpj_view.read_overview(bad)
    with pytest.raises(ValueError, match="нет проекта"):
        xpj_view.read_overview(tmp_path / "Nope.xpj")
    project = build(make_plan(), tmp_path)
    broken = xpj.load(project)
    del broken.data["sequences"]
    path = tmp_path / "NoSeq.xpj"
    path.write_bytes(xpj.pack(xpj.render(broken)))
    with pytest.raises(ValueError, match="не удалось прочитать"):
        xpj_view.read_overview(path)


def test_summarize_service_tracks_hidden_and_other_types_shown_without_pads() -> None:
    def drum_track(name: str, type_: int) -> dict:
        pads = [{"layersv": [{"sampleName": "", "sampleFile": ""}]} for _ in range(128)]
        return {"name": name, "program": {"type": type_, "drum": {"instruments": pads}, "padNoteMap": {"noteForPad": {}}}}

    data = {
        "tracks": [drum_track("HANDS", 0), drum_track("Keys", 1), drum_track("Plug", 3), drum_track("Mid", 4),
                   drum_track("Submix 1", 8), drum_track("Return 1", 7), drum_track("Out 1", 9)],
        "sequences": [{"key": 0, "value": {"name": "A", "lengthBars": 4}}],
        "samples": [],
    }
    view = summarize(data, {})
    assert [(t["name"], t["kind"]) for t in view["tracks"]] == [
        ("HANDS", "drum"), ("Keys", "keygroup"), ("Plug", "plugin"), ("Mid", "midi"),
    ]
    assert all(t["pads"] == [] for t in view["tracks"])


@pytest.fixture
def version(tmp_path: Path) -> Path:
    folder = tmp_path / "plan" / "v1"
    plan = make_plan()
    write_samples(plan, folder / "samples")
    (folder / "plan.json").write_text(to_json(plan), encoding="utf-8")
    return folder


@pytest.fixture
def client(version: Path, tmp_path: Path) -> TestClient:
    out = tmp_path / "result"
    out.mkdir()
    return TestClient(web.create_app(Session(version), out, "Song"), base_url=HOST)


def test_web_project_is_refused_before_build_and_served_after(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/state").json()["built"] is None
    assert client.get("/api/project").status_code == 409
    assert client.post("/api/finish").status_code == 200
    state = client.get("/api/state").json()
    assert state["built"] == str(tmp_path / "result" / "Song.xpj")
    view = client.get("/api/project").json()
    assert [t["name"] for t in view["tracks"]][:2] == ["HANDS", "Drums"]


def test_web_project_audio_serves_only_files_used_by_pads(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/finish")
    data = tmp_path / "result" / "Song_[ProjectData]"
    (data / "stray.wav").write_bytes(b"RIFF....")
    (tmp_path / "result" / "Secret.wav").write_bytes(b"RIFF....")
    ok = client.get("/api/project/audio", params={"name": "ELA_DR_Kick_01.wav"})
    assert ok.status_code == 200 and ok.content[:4] == b"RIFF"
    for name in ("stray.wav", "../Secret.wav", "../Song.xpj", "Nope.wav", ""):
        assert client.get("/api/project/audio", params={"name": name}).status_code == 404


def test_web_project_endpoints_refuse_foreign_host_and_origin(client: TestClient) -> None:
    client.post("/api/finish")
    assert client.get("/api/project", headers={"host": "evil.example"}).status_code == 403
    assert client.get("/api/project/audio", params={"name": "x.wav"}, headers={"origin": "http://evil.example"}).status_code == 403


def test_web_project_after_rebuild_shows_new_state(client: TestClient) -> None:
    client.post("/api/finish")
    client.post("/api/edit", json=merge())
    client.post("/api/finish", json={"overwrite": True})
    view = client.get("/api/project").json()
    assert next(t for t in view["tracks"] if t["name"] == "Drums")["filled"] == 3


def tamper(project: Path, sample_file: str) -> None:
    loaded = xpj.load(project)
    drums = next(t for t in loaded.data["tracks"] if t["name"] == "Drums")
    drums["program"]["drum"]["instruments"][0]["layersv"][0]["sampleFile"] = sample_file
    project.write_bytes(xpj.pack(xpj.render(loaded)))


@pytest.mark.parametrize("kind", ["parent", "absolute", "symlink"])
def test_web_project_audio_refuses_files_outside_data_folder_even_if_project_points_there(
    client: TestClient, tmp_path: Path, kind: str
) -> None:
    client.post("/api/finish")
    result = tmp_path / "result"
    secret = result / "Secret.wav"
    secret.write_bytes(b"RIFF....")
    data = result / "Song_[ProjectData]"
    name = {"parent": "../Secret.wav", "absolute": str(secret), "symlink": "link.wav"}[kind]
    if kind == "symlink":
        (data / "link.wav").symlink_to(secret)
    tamper(result / "Song.xpj", name)
    assert client.get("/api/project/audio", params={"name": name}).status_code == 404


def test_read_overview_folder_errors_are_value_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = build(make_plan(), tmp_path)

    def denied(self):
        raise PermissionError("нет прав")

    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(ValueError, match="не удалось прочитать"):
        xpj_view.read_overview(project)
