"""AN-070, AN-062: сессия правок, сохранение версии, сервер."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from logic2mpc.adapters import web
from logic2mpc.app import BusyError, ConfirmationError, ExportTargetError, Session, confirm
from logic2mpc.core.edit import EditError
from logic2mpc.core.plan import to_json

from test_edit import make_plan, merge


@pytest.fixture
def version(tmp_path: Path) -> Path:
    folder = tmp_path / "plan" / "v1"
    (folder / "samples").mkdir(parents=True)
    plan = make_plan()
    for g in plan.groups:
        for t in g.tracks:
            for i, p in enumerate(t.pieces):
                sf.write(folder / "samples" / p.file, np.full((480, 2), 0.01 * (i + 1)), 48000, subtype="PCM_24")
    (folder / "plan.json").write_text(to_json(plan), encoding="utf-8")
    (folder / "report.md").write_text("old\n", encoding="utf-8")
    return folder


def digest(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


def test_an062_save_writes_next_version_and_keeps_old_one(version: Path) -> None:
    before = digest(version)
    session = Session(version)
    session.edit(merge())
    saved = session.save()
    assert saved.name == "v2"
    assert digest(version) == before
    assert (saved / "plan.json").is_file() and (saved / "report.md").is_file()
    assert "объединён в ELA_DR_Kick_01" in (saved / "report.md").read_text(encoding="utf-8")


def test_an062_save_does_not_inherit_confirmation(version: Path) -> None:
    confirm(version)
    session = Session(version)
    session.edit(merge())
    saved = session.save()
    assert (version / "confirmed.json").is_file()
    assert not (saved / "confirmed.json").exists()


def test_an070_save_renames_sample_files_and_keeps_merged_away_ones(version: Path) -> None:
    session = Session(version)
    session.edit(merge())
    session.edit({"op": "move_track", "track": 3, "to": "Synth"})
    saved = session.save()
    files = sorted(p.name for p in (saved / "samples").glob("*.wav"))
    assert "ELA_SY_Bass_02.wav" in files and "ELA_SY_Bass_03.wav" in files
    assert "ELA_BS_Bass_01.wav" not in files
    assert "ELA_DR_Kick_02.wav" in files
    old, new = sf.read(version / "samples" / "ELA_BS_Bass_01.wav")[0], sf.read(saved / "samples" / "ELA_SY_Bass_02.wav")[0]
    assert np.allclose(old, new)


def test_an070_edits_are_kept_in_memory_until_save(version: Path) -> None:
    session = Session(version)
    session.edit(merge())
    assert session.dirty
    assert not (version.parent / "v2").exists()
    session.save()
    assert not session.dirty


def test_an070_refused_edit_changes_nothing(version: Path) -> None:
    session = Session(version)
    with pytest.raises(EditError):
        session.edit(merge(sources=["ELA_DR_Snare_01"]))
    assert not session.dirty


def test_an070_undo_restores_previous_state(version: Path) -> None:
    session = Session(version)
    session.edit(merge())
    session.edit({"op": "rename_group", "group": "Synth", "name": "Pads"})
    session.undo()
    assert [g.name for g in session.plan.groups] == ["Drums", "Bass", "Synth", "Lead"]
    session.undo()
    assert not session.dirty
    with pytest.raises(EditError):
        session.undo()


def test_an070_audio_of_renamed_piece_comes_from_original_file(version: Path) -> None:
    session = Session(version)
    session.edit({"op": "move_track", "track": 3, "to": "Synth"})
    path = session.audio("ELA_SY_Bass_02")
    assert path == version / "samples" / "ELA_BS_Bass_01.wav"
    with pytest.raises(KeyError):
        session.audio("../plan")


def test_an062_confirm_and_build_are_refused_while_edits_are_unsaved(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.edit(merge())
    with pytest.raises(ConfirmationError):
        session.confirm()
    with pytest.raises(ConfirmationError):
        session.build(tmp_path / "out", "Song")


def test_an070_saved_version_builds_after_confirm(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.edit(merge())
    session.save()
    with pytest.raises(ConfirmationError):
        session.build(tmp_path / "out", "Song")
    session.confirm()
    project = session.build(tmp_path / "out", "Song")
    assert project.name == "Song.xpj"
    assert (tmp_path / "out" / "Song_[ProjectData]" / "ELA_DR_Kick_01.wav").is_file()
    assert not (tmp_path / "out" / "Song_[ProjectData]" / "ELA_DR_Kick_02.wav").exists()


@pytest.fixture
def client(version: Path, tmp_path: Path) -> TestClient:
    (tmp_path / "out").mkdir()
    return TestClient(web.create_app(Session(version), tmp_path / "out", "Song"), base_url="http://127.0.0.1:8765")


def test_web_listens_only_on_localhost(version: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(web.uvicorn, "run", lambda app, **kwargs: seen.update(kwargs))
    web.serve(Session(version), tmp_path, "Song", 8765, open_browser=False)
    assert seen["host"] == "127.0.0.1"


def test_web_refuses_foreign_host_and_origin(client: TestClient) -> None:
    assert client.get("/api/state", headers={"host": "evil.example"}).status_code == 403
    assert client.post("/api/save", headers={"origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/save", headers={"origin": "http://127.0.0.1:8765"}).status_code == 200
    assert client.get("/api/state", headers={"host": "localhost:8765"}).status_code == 200


def test_web_state_has_plan_and_flags(client: TestClient) -> None:
    state = client.get("/api/state").json()
    assert state["version"] == "v1"
    assert state["dirty"] is False
    assert [g["name"] for g in state["plan"]["groups"]] == ["Drums", "Bass", "Synth", "Lead"]


def test_web_edit_refusal_is_400_with_text(client: TestClient) -> None:
    answer = client.post("/api/edit", json=merge(sources=["ELA_DR_Snare_01"]))
    assert answer.status_code == 400
    assert answer.json()["error"]
    assert client.get("/api/state").json()["dirty"] is False


def test_web_edit_undo_save(client: TestClient) -> None:
    assert client.post("/api/edit", json=merge()).json()["dirty"] is True
    assert client.post("/api/undo").json()["dirty"] is False
    client.post("/api/edit", json=merge())
    state = client.post("/api/save").json()
    assert state["version"] == "v2" and state["dirty"] is False


def test_web_audio_serves_piece_wav_and_refuses_unknown_names(client: TestClient) -> None:
    answer = client.get("/api/audio", params={"name": "ELA_DR_Kick_01"})
    assert answer.status_code == 200
    assert answer.content[:4] == b"RIFF"
    assert client.get("/api/audio", params={"name": "../plan.json"}).status_code == 404
    assert client.get("/api/audio", params={"name": "Nope"}).status_code == 404
    assert client.get("/api/audio", params={"name": "plan"}).status_code == 404


def test_web_build_needs_confirm_then_creates_project(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/edit", json=merge())
    assert client.post("/api/confirm").status_code == 409
    client.post("/api/save")
    assert client.post("/api/build").status_code == 409
    assert client.post("/api/confirm").status_code == 200
    answer = client.post("/api/build")
    assert answer.status_code == 200
    assert (tmp_path / "out" / "Song.xpj").is_file()
    assert json.loads(answer.text)["project"].endswith("Song.xpj")


def test_web_page_is_served(client: TestClient) -> None:
    answer = client.get("/")
    assert answer.status_code == 200
    assert "<html" in answer.text


def test_target_paths_are_built_from_folder_and_name_with_transliteration(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    assert session.target()["project"] is None
    session.set_target(tmp_path, "Песня.xpj")
    target = session.target()
    assert target["name"] == "Песня"
    assert target["project"] == str(tmp_path / "Pesnya.xpj")
    assert target["data"] == str(tmp_path / "Pesnya_[ProjectData]")
    assert target["exists"] is False


@pytest.mark.parametrize("name", ["", "   ", "a/b", "..", ".", ".xpj"])
def test_target_refuses_bad_names(version: Path, tmp_path: Path, name: str) -> None:
    with pytest.raises(ExportTargetError):
        Session(version).set_target(tmp_path, name)


def test_target_refuses_missing_folder(version: Path, tmp_path: Path) -> None:
    with pytest.raises(ExportTargetError):
        Session(version).set_target(tmp_path / "nope", "Song")


def test_target_name_alone_keeps_folder(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.set_target(tmp_path, "Song")
    session.set_target(None, "Other")
    assert session.target()["project"] == str(tmp_path / "Other.xpj")


def test_finish_saves_confirms_and_builds_into_chosen_folder(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.edit(merge())
    folder = tmp_path / "result"
    folder.mkdir()
    session.set_target(folder, "Мой")
    project = session.finish()
    assert project == folder / "Moy.xpj"
    assert (folder / "Moy_[ProjectData]" / "ELA_DR_Kick_01.wav").is_file()
    assert session.version.name == "v2" and not session.dirty and session.confirmed
    assert session.target()["exists"] is True


def test_finish_without_edits_uses_current_version(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.set_target(tmp_path, "Song")
    session.finish()
    assert session.version.name == "v1"
    assert (tmp_path / "Song.xpj").is_file()


def test_finish_without_folder_is_refused_and_saves_nothing(version: Path) -> None:
    session = Session(version)
    session.edit(merge())
    with pytest.raises(ExportTargetError):
        session.finish()
    assert session.dirty and not (version.parent / "v2").exists()


def test_pick_folder_runs_system_dialog_and_strips_the_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Done:
        returncode, stdout = 0, "/Users/x/Music/\n"

    monkeypatch.setattr(web.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or Done())
    assert web.pick_folder() == Path("/Users/x/Music")
    assert calls[0][0] == "osascript" and "choose folder" in calls[0][-1]


def test_pick_folder_returns_none_on_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cancelled:
        returncode, stdout = 1, ""

    monkeypatch.setattr(web.subprocess, "run", lambda cmd, **kw: Cancelled())
    assert web.pick_folder() is None


@pytest.fixture
def picked(version: Path, tmp_path: Path) -> tuple[TestClient, dict]:
    chosen: dict = {"folder": None}
    app = web.create_app(Session(version), None, None, picker=lambda: chosen["folder"])
    return TestClient(app, base_url="http://127.0.0.1:8765"), chosen


def test_web_export_panel_state_and_updates(picked: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = picked
    export = client.get("/api/state").json()["export"]
    assert export["folder"] is None and export["name"] == "ELA" and export["project"] is None
    state = client.post("/api/export", json={"folder": str(tmp_path), "name": "Песня"}).json()
    assert state["export"]["project"] == str(tmp_path / "Pesnya.xpj")
    assert client.post("/api/export", json={"name": "a/b"}).status_code == 400
    assert client.post("/api/export", json={"folder": str(tmp_path / "nope")}).status_code == 400
    assert client.get("/api/state").json()["export"]["name"] == "Песня"


def test_web_pick_folder_sets_folder_and_cancel_keeps_it(picked: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, chosen = picked
    chosen["folder"] = tmp_path
    assert client.post("/api/pick-folder").json()["export"]["folder"] == str(tmp_path)
    chosen["folder"] = None
    assert client.post("/api/pick-folder").json()["export"]["folder"] == str(tmp_path)


def test_web_finish_builds_project_after_edit(picked: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = picked
    client.post("/api/edit", json=merge())
    assert client.post("/api/finish").status_code == 400
    client.post("/api/export", json={"folder": str(tmp_path), "name": "Song"})
    answer = client.post("/api/finish")
    assert answer.status_code == 200
    assert (tmp_path / "Song.xpj").is_file()
    state = client.get("/api/state").json()
    assert state["version"] == "v2" and state["export"]["exists"] is True


def test_web_new_endpoints_refuse_foreign_origin(picked: tuple[TestClient, dict]) -> None:
    client, _ = picked
    for path in ("/api/export", "/api/pick-folder", "/api/finish"):
        assert client.post(path, json={}, headers={"origin": "http://evil.example"}).status_code == 403


def test_finish_refuses_to_overwrite_existing_project_without_flag(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.set_target(tmp_path, "Song")
    session.finish()
    session.edit(merge())
    with pytest.raises(ExportTargetError, match="уже есть"):
        session.finish()
    assert session.dirty and not (version.parent / "v2").exists()
    assert session.finish(overwrite=True) == tmp_path / "Song.xpj"


@pytest.mark.parametrize("name", ["ь", "ъь", ".hidden", "a\\b", "a\nb"])
def test_target_refuses_names_that_are_empty_after_transliteration_or_unsafe(version: Path, tmp_path: Path, name: str) -> None:
    with pytest.raises(ExportTargetError):
        Session(version).set_target(tmp_path, name)


def test_target_refuses_relative_folder_and_expands_home(version: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ExportTargetError):
        Session(version).set_target(Path("relative"), "Song")
    monkeypatch.setenv("HOME", str(tmp_path))
    session = Session(version)
    session.set_target(Path("~"), "Song")
    assert session.target()["folder"] == str(tmp_path.resolve())


def test_save_failure_leaves_no_half_written_version(version: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = Session(version)
    session.edit(merge())

    def broken(*args, **kwargs):
        raise PermissionError("нет прав")

    monkeypatch.setattr("logic2mpc.app.shutil.copy2", broken)
    with pytest.raises(PermissionError):
        session.save()
    assert not (version.parent / "v2").exists()
    assert session.dirty


def test_web_finish_and_build_need_overwrite_flag_for_existing_project(picked: tuple[TestClient, dict], tmp_path: Path) -> None:
    client, _ = picked
    client.post("/api/export", json={"folder": str(tmp_path), "name": "Song"})
    assert client.post("/api/finish").status_code == 200
    assert client.post("/api/finish").status_code == 409
    assert client.post("/api/build").status_code == 409
    assert client.post("/api/finish", json={"overwrite": True}).status_code == 200


def test_web_os_errors_and_wrong_types_are_json_errors(picked: tuple[TestClient, dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = picked
    for body in ({"folder": 5}, {"name": 5}, {"folder": ["x"]}):
        answer = client.post("/api/export", json=body)
        assert answer.status_code == 400 and answer.json()["error"]
    client.post("/api/export", json={"folder": str(tmp_path), "name": "Song"})
    monkeypatch.setattr("logic2mpc.app.build_result", lambda *a, **k: (_ for _ in ()).throw(PermissionError("нет прав")))
    answer = client.post("/api/finish")
    assert answer.status_code == 400 and "нет прав" in answer.json()["error"]


def test_web_pick_folder_without_osascript_is_json_error(version: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args, **kwargs):
        raise FileNotFoundError("osascript")

    monkeypatch.setattr(web.subprocess, "run", missing)
    client = TestClient(web.create_app(Session(version), None, None), base_url="http://127.0.0.1:8765")
    answer = client.post("/api/pick-folder")
    assert answer.status_code == 400 and answer.json()["error"]


def test_overwrite_replaces_old_project_and_its_data_folder_completely(version: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    session = Session(version)
    session.set_target(out, "Song")
    session.finish()
    data = out / "Song_[ProjectData]"
    assert (data / "ELA_DR_Kick_02.wav").is_file()
    (data / "stray.txt").write_text("old", encoding="utf-8")
    session.edit(merge())
    session.finish(overwrite=True)
    assert not (data / "ELA_DR_Kick_02.wav").exists()
    assert not (data / "stray.txt").exists()
    assert (data / "ELA_DR_Kick_01.wav").is_file()
    assert sorted(p.name for p in out.iterdir()) == ["Song.xpj", "Song_[ProjectData]"]


def test_failed_overwrite_keeps_old_project_and_leaves_no_temp_folder(version: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out"
    out.mkdir()
    session = Session(version)
    session.set_target(out, "Song")
    session.finish()
    before = digest(out)

    def broken(plan, samples, out, name):
        (out / "half.txt").write_text("x", encoding="utf-8")
        raise FileNotFoundError("нет сэмплов: X")

    monkeypatch.setattr("logic2mpc.app.xpj.export_project", broken)
    with pytest.raises(FileNotFoundError):
        session.build(out, "Song")
    assert digest(out) == before
    assert sorted(p.name for p in out.iterdir()) == ["Song.xpj", "Song_[ProjectData]"]


def test_finish_while_another_finish_runs_is_refused_and_changes_nothing(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    session.set_target(tmp_path, "Song")
    session.edit(merge())
    with session.lock:
        with pytest.raises(BusyError):
            session.finish()
    assert session.dirty and not (version.parent / "v2").exists()
    session.finish()
    assert session.version.name == "v2"


def test_web_second_finish_during_build_is_409(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    client = TestClient(web.create_app(session, tmp_path, "Song"), base_url="http://127.0.0.1:8765")
    with session.lock:
        answer = client.post("/api/finish")
        assert answer.status_code == 409 and "идёт" in answer.json()["error"]
        assert client.post("/api/build").status_code == 409
    assert client.post("/api/finish").status_code == 200


def test_web_state_tells_when_build_is_running(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    client = TestClient(web.create_app(session, tmp_path, "Song"), base_url="http://127.0.0.1:8765")
    assert client.get("/api/state").json()["busy"] is False
    with session.lock:
        assert client.get("/api/state").json()["busy"] is True


def test_edits_are_refused_while_build_runs(version: Path, tmp_path: Path) -> None:
    session = Session(version)
    client = TestClient(web.create_app(session, tmp_path, "Song"), base_url="http://127.0.0.1:8765")
    with session.lock:
        assert client.post("/api/edit", json=merge()).status_code == 409
        assert client.post("/api/undo").status_code == 409
    assert not session.dirty
