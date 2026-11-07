"""AN-071, S-013: стартовый экран, анализ из интерфейса, группы по умолчанию."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from logic2mpc import app
from logic2mpc.adapters import logic, web
from logic2mpc.app import BusyError, Workspace, find_version, inspect_project
from logic2mpc.core.model import AudioRegion, Track
from logic2mpc.core.plan import from_json

HOST = "http://127.0.0.1:8765"


def tone(frames: int = 96000) -> np.ndarray:
    wave = 0.5 * np.sin(np.arange(frames) * 0.05)
    return np.stack([wave, wave], axis=1)


def tracks() -> list[Track]:
    return [
        Track(0, "Kick", "Drums", [], [AudioRegion(0)]),
        Track(1, "Sub", "Bass", [], [AudioRegion(0)]),
        Track(2, "Lone", None, [], [AudioRegion(0)]),
    ]


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    song = logic.Song(120.0, 48000, tracks(), [(0, "Intro")], 0, 0)
    monkeypatch.setattr(logic, "read_project", lambda _: song)
    project = tmp_path / "Fuzz - Elated.logicx"
    project.mkdir()
    export = tmp_path / "export"
    export.mkdir()
    for number in (1, 2, 3):
        sf.write(export / f"{number:02d}_T.wav", tone(), 48000, subtype="PCM_24")
    return project, export


def test_an071_analyze_without_groups_file_builds_groups_from_stacks(setup: tuple[Path, Path]) -> None:
    project, export = setup
    folder = app.analyze(project, export, None, export / "plan", song="ELA")
    plan = from_json((folder / "plan.json").read_text(encoding="utf-8"))
    assert [(g.name, g.code) for g in plan.groups] == [("Drums", "DR"), ("Bass", "BS"), ("Прочее", "OT")]
    assert plan.song == "ELA"
    assert (folder / "samples" / "ELA_DR_Kick_01.wav").is_file()


def test_an071_analyze_without_song_uses_project_name(setup: tuple[Path, Path]) -> None:
    project, export = setup
    folder = app.analyze(project, export, None, export / "plan")
    assert from_json((folder / "plan.json").read_text(encoding="utf-8")).song == "ELA"


def test_analyze_reports_progress_for_every_track_in_order(setup: tuple[Path, Path]) -> None:
    project, export = setup
    seen: list[tuple[int, int, str]] = []
    app.analyze(project, export, None, export / "plan", progress=lambda done, total, name: seen.append((done, total, name)))
    assert [(d, t) for d, t, _ in seen] == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert [n for _, _, n in seen[:3]] == ["Kick", "Sub", "Lone"]


def test_inspect_project_summarises_groups_and_missing_export(setup: tuple[Path, Path]) -> None:
    project, export = setup
    (export / "03_T.wav").unlink()
    info = inspect_project(project, export)
    assert info["song"] == "ELA" and info["name"] == "Fuzz - Elated"
    assert [(g["name"], g["code"], g["tracks"]) for g in info["groups"]] == [
        ("Drums", "DR", 1), ("Bass", "BS", 1), ("Прочее", "OT", 1),
    ]
    assert info["missing"] == ["Lone"]
    assert info["tracks"] == 3


def test_inspect_project_refuses_bad_paths(setup: tuple[Path, Path], tmp_path: Path) -> None:
    project, export = setup
    with pytest.raises(ValueError, match="logicx"):
        inspect_project(tmp_path / "x.txt", export)
    with pytest.raises(ValueError, match="нет"):
        inspect_project(tmp_path / "No.logicx", export)
    with pytest.raises(ValueError, match="экспорт"):
        inspect_project(project, tmp_path / "nope")


def test_find_version_picks_file_or_latest_numeric(tmp_path: Path) -> None:
    (tmp_path / "plan.json").write_text("{}", encoding="utf-8")
    assert find_version(tmp_path) == tmp_path
    folder = tmp_path / "plans"
    for name in ("v2", "v10", "v9", "notes"):
        (folder / name).mkdir(parents=True)
    assert find_version(folder) == folder / "v10"
    (tmp_path / "empty").mkdir()
    assert find_version(tmp_path / "empty") is None
    assert find_version(tmp_path / "missing") is None


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(web.create_app(None, None, None), base_url=HOST)


@pytest.mark.web
def test_web_without_session_is_start_mode_and_refuses_edit_and_build(client: TestClient) -> None:
    state = client.get("/api/state").json()
    assert state["mode"] == "start" and state["job"]["running"] is False
    assert client.post("/api/edit", json={"op": "rename_group"}).status_code == 409
    assert client.post("/api/finish").status_code == 409
    assert client.post("/api/export", json={"name": "x"}).status_code == 409
    assert client.get("/api/audio", params={"name": "x"}).status_code == 404


@pytest.mark.web
def test_web_start_endpoints_refuse_foreign_origin(client: TestClient) -> None:
    for path in ("/api/inspect", "/api/analyze", "/api/pick-logic", "/api/pick-export"):
        assert client.post(path, json={}, headers={"origin": "http://evil.example"}).status_code == 403


@pytest.mark.web
def test_web_inspect_bad_path_is_json_error(client: TestClient, tmp_path: Path) -> None:
    answer = client.post("/api/inspect", json={"project": str(tmp_path / "x.txt"), "export": str(tmp_path)})
    assert answer.status_code == 400 and answer.json()["error"]
    assert client.post("/api/inspect", json={"project": 5, "export": None}).status_code == 400


@pytest.mark.web
def test_web_inspect_returns_summary(setup: tuple[Path, Path]) -> None:
    project, export = setup
    client = TestClient(web.create_app(None, None, None), base_url=HOST)
    answer = client.post("/api/inspect", json={"project": str(project), "export": str(export)})
    assert answer.status_code == 200 and answer.json()["song"] == "ELA"


def wait(client: TestClient) -> dict:
    for _ in range(200):
        state = client.get("/api/state").json()
        if not state["job"]["running"]:
            return state
        time.sleep(0.05)
    raise AssertionError("анализ не закончился")


@pytest.mark.web
def test_web_analyze_runs_in_background_then_opens_editor(setup: tuple[Path, Path]) -> None:
    project, export = setup
    client = TestClient(web.create_app(None, None, None), base_url=HOST)
    answer = client.post("/api/analyze", json={"project": str(project), "export": str(export), "song": "ELX"})
    assert answer.status_code == 200
    state = wait(client)
    assert state["mode"] == "edit" and state["job"]["error"] is None
    assert state["job"]["done"] == state["job"]["total"] == 3
    assert state["version"] == "v1"
    assert state["plan"]["song"] == "ELX"
    assert (export / "plan" / "v1" / "plan.json").is_file()
    assert state["export"]["name"] == "Fuzz - Elated"
    assert client.get("/api/audio", params={"name": "ELX_DR_Kick_01"}).status_code == 200


@pytest.mark.web
def test_web_second_analyze_during_first_is_409_and_error_is_in_job(setup: tuple[Path, Path], tmp_path: Path) -> None:
    project, export = setup
    release = []

    def slow(*args, progress=None, **kwargs):
        while not release:
            time.sleep(0.02)
        raise ValueError("анализ не удался")

    client = TestClient(web.create_app(None, None, None, analyzer=slow), base_url=HOST)
    body = {"project": str(project), "export": str(export), "song": "ELA"}
    assert client.post("/api/analyze", json=body).status_code == 200
    assert client.post("/api/analyze", json=body).status_code == 409
    release.append(1)
    state = wait(client)
    assert state["mode"] == "start" and "анализ не удался" in state["job"]["error"]


@pytest.mark.web
def test_web_pickers_fill_paths_and_cancel_returns_none(setup: tuple[Path, Path]) -> None:
    project, export = setup
    chosen = {"logic": project, "export": export}
    client = TestClient(
        web.create_app(None, None, None, picker=lambda: chosen["export"], logic_picker=lambda: chosen["logic"]), base_url=HOST,
    )
    assert client.post("/api/pick-logic").json()["path"] == str(project)
    assert client.post("/api/pick-export").json()["path"] == str(export)
    chosen["logic"] = None
    assert client.post("/api/pick-logic").json()["path"] is None


def test_workspace_refuses_second_start_while_running(setup: tuple[Path, Path]) -> None:
    project, export = setup
    gate = []

    def blocked(*args, progress=None, **kwargs):
        while not gate:
            time.sleep(0.02)
        return app.analyze(*args, progress=progress, **kwargs)

    workspace = Workspace(None, analyzer=blocked)
    workspace.start(project, export, "ELA")
    with pytest.raises(BusyError):
        workspace.start(project, export, "ELA")
    gate.append(1)
    workspace.join()
    assert workspace.session is not None
    shutil.rmtree(export / "plan")


@pytest.mark.parametrize("song", ["../../X", "AB", "ABCD", "abc", "ПЕС", "A/B", ""])
def test_song_code_must_be_three_latin_capitals(setup: tuple[Path, Path], song: str) -> None:
    project, export = setup
    with pytest.raises(ValueError, match="код песни"):
        app.analyze(project, export, None, export / "plan", song=song)
    assert not (export / "plan").exists()
    client = TestClient(web.create_app(None, None, None), base_url=HOST)
    answer = client.post("/api/analyze", json={"project": str(project), "export": str(export), "song": song})
    if song.upper() in {"ABC"}:
        assert answer.status_code == 200
        wait(client)
        return
    assert answer.status_code == 400 and "код песни" in answer.json()["error"]
    assert not (export / "plan").exists() and not list(export.parent.glob("*_DR_*.wav"))


def test_analyze_refused_while_a_plan_is_open(setup: tuple[Path, Path]) -> None:
    project, export = setup
    client = TestClient(web.create_app(None, None, None), base_url=HOST)
    body = {"project": str(project), "export": str(export), "song": "ELA"}
    client.post("/api/analyze", json=body)
    wait(client)
    client.post("/api/edit", json={"op": "rename_group", "group": "Drums", "name": "Perc"})
    assert client.post("/api/analyze", json=body).status_code == 409
    state = client.get("/api/state").json()
    assert state["dirty"] is True and state["plan"]["groups"][0]["name"] == "Perc"


def test_project_without_audible_tracks_is_refused(setup: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    project, export = setup
    empty = logic.Song(120.0, 48000, [Track(0, "Off", "Drums", [], [AudioRegion(0, muted=True)])], [], 0, 0)
    monkeypatch.setattr(logic, "read_project", lambda _: empty)
    with pytest.raises(ValueError, match="нет дорожек со звуком"):
        inspect_project(project, export)
    with pytest.raises(ValueError, match="нет дорожек со звуком"):
        Workspace(None).start(project, export, "ELA")


def test_an071_analysis_without_file_equals_analysis_with_equivalent_file(setup: tuple[Path, Path], tmp_path: Path) -> None:
    project, export = setup
    groups = tmp_path / "groups.json"
    groups.write_text(json.dumps({"song": "ELA", "groups": {
        "Drums": {"code": "DR", "method": "drum"}, "Bass": {"code": "BS", "method": "drum"}, "Прочее": {"code": "OT", "method": "drum"},
    }}), encoding="utf-8")
    with_file = from_json((app.analyze(project, export, groups, tmp_path / "a") / "plan.json").read_text(encoding="utf-8"))
    without = from_json((app.analyze(project, export, None, tmp_path / "b", song="ELA") / "plan.json").read_text(encoding="utf-8"))
    assert without == with_file


def test_analyze_leaves_out_groups_without_tracks(setup: tuple[Path, Path], tmp_path: Path) -> None:
    project, export = setup
    groups = tmp_path / "groups.json"
    groups.write_text(json.dumps({"song": "ELA", "groups": {
        "Drums": {"code": "DR"}, "Bass": {"code": "BS"}, "Strings": {"code": "ST"},
    }}), encoding="utf-8")
    plan = from_json((app.analyze(project, export, groups, tmp_path / "a") / "plan.json").read_text(encoding="utf-8"))
    assert [g.name for g in plan.groups] == ["Drums", "Bass", "Прочее"]


def opened(setup: tuple[Path, Path]) -> tuple[TestClient, Path, Path]:
    project, export = setup
    client = TestClient(web.create_app(None, None, None), base_url=HOST)
    client.post("/api/analyze", json={"project": str(project), "export": str(export), "song": "ELA"})
    wait(client)
    return client, project, export


def test_close_returns_to_start_screen_and_keeps_files(setup: tuple[Path, Path]) -> None:
    client, project, export = opened(setup)
    answer = client.post("/api/close")
    assert answer.status_code == 200 and answer.json()["mode"] == "start"
    assert client.get("/api/state").json()["mode"] == "start"
    assert (export / "plan" / "v1" / "plan.json").is_file()
    assert client.post("/api/edit", json={"op": "rename_group"}).status_code == 409


def test_close_with_unsaved_edits_needs_discard_flag(setup: tuple[Path, Path]) -> None:
    client, _, _ = opened(setup)
    client.post("/api/edit", json={"op": "rename_group", "group": "Drums", "name": "Perc"})
    answer = client.post("/api/close")
    assert answer.status_code == 409 and "несохранённые" in answer.json()["error"]
    assert client.get("/api/state").json()["mode"] == "edit"
    assert client.post("/api/close", json={"discard": True}).json()["mode"] == "start"


def test_close_during_build_is_refused(setup: tuple[Path, Path]) -> None:
    client, _, _ = opened(setup)
    with client.app.state.workspace.session.lock:
        assert client.post("/api/close", json={"discard": True}).status_code == 409
    assert client.get("/api/state").json()["mode"] == "edit"


def test_after_close_a_new_analysis_can_start(setup: tuple[Path, Path]) -> None:
    client, project, export = opened(setup)
    client.post("/api/close")
    body = {"project": str(project), "export": str(export), "song": "ELA"}
    assert client.post("/api/analyze", json=body).status_code == 200
    state = wait(client)
    assert state["mode"] == "edit" and state["version"] == "v2"


def test_close_without_plan_is_a_noop(client: TestClient) -> None:
    assert client.post("/api/close").json()["mode"] == "start"


def test_close_refuses_foreign_origin(client: TestClient) -> None:
    assert client.post("/api/close", headers={"origin": "http://evil.example"}).status_code == 403


def test_analyze_prints_nothing_to_terminal(setup: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    project, export = setup
    app.analyze(project, export, None, export / "plan")
    assert capsys.readouterr().out == ""
