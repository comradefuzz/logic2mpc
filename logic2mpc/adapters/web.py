"""Браузерный интерфейс правки плана. Тонкий слой над `app.Session`, логики правок здесь нет."""
from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from pathlib import Path

import uvicorn
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from . import xpj
from ..app import BusyError, ConfirmationError, ExportTargetError, Session, Workspace, inspect_project
from ..core import edit as editing
from ..core import report
from ..core.plan import is_exported, to_json

HOST = "127.0.0.1"
PAGE = Path(__file__).resolve().parent.parent / "web" / "index.html"


def state(session: Session | None, job: dict | None = None) -> dict:
    job = job or {"running": False, "done": 0, "total": 0, "track": "", "error": None}
    if session is None:
        return {"mode": "start", "job": job}
    pads = {g.name: sum(is_exported(p) for t in g.tracks for p in t.pieces) for g in session.plan.groups}
    return {
        "mode": "edit",
        "job": job,
        "version": session.version.name,
        "dirty": session.dirty,
        "confirmed": session.confirmed,
        "busy": session.busy,
        "plan": json.loads(to_json(session.plan)),
        "pads": pads,
        "export": session.target(),
        "built": str(session.built) if session.built else None,
    }


def osascript(script: str) -> Path | None:
    """Системное окно macOS. Браузер полного пути не отдаёт, окно открывает сервер."""
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    except OSError as error:
        raise ExportTargetError(f"системное окно недоступно: {error}") from None
    text = result.stdout.strip()
    return Path(text) if result.returncode == 0 and text else None


def pick_folder() -> Path | None:
    return osascript('POSIX path of (choose folder with prompt "Выберите папку")')


def pick_logic() -> Path | None:
    return osascript('POSIX path of (choose file with prompt "Проект Logic (.logicx)")')


def create_app(
    session: Session | None, out: Path | None, name: str | None, picker=pick_folder, *, logic_picker=pick_logic, analyzer=None,
) -> FastAPI:
    app = FastAPI()
    ws = Workspace(session, analyzer)
    app.state.workspace = ws
    if session is not None and (out is not None or name is not None):
        session.set_target(out, name)
    local = {HOST, "localhost"}

    @app.middleware("http")
    async def only_local_pages(request: Request, call_next):
        """Защита от чужих страниц в браузере: Host и Origin должны быть локальными."""
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if urlsplit(f"//{host}").hostname not in local:
            return JSONResponse({"error": "чужой Host"}, status_code=403)
        if origin is not None and (urlsplit(origin).hostname not in local or urlsplit(origin).netloc != host):
            return JSONResponse({"error": "чужой Origin"}, status_code=403)
        return await call_next(request)

    def refuse(error: Exception, status: int) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=status)

    def no_plan() -> JSONResponse:
        return refuse(RuntimeError("план не открыт: сначала анализ"), 409)

    def current() -> dict:
        return state(ws.session, dict(ws.job))

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/state")
    def get_state() -> dict:
        return current()

    @app.get("/api/report", response_class=PlainTextResponse)
    def get_report():
        if ws.session is None:
            return no_plan()
        return report.render(ws.session.plan)

    @app.post("/api/pick-logic")
    def post_pick_logic():
        try:
            path = logic_picker()
        except ExportTargetError as error:
            return refuse(error, 400)
        return {"path": str(path) if path else None}

    @app.post("/api/pick-export")
    def post_pick_export():
        try:
            path = picker()
        except ExportTargetError as error:
            return refuse(error, 400)
        return {"path": str(path) if path else None}

    def paths(body: dict) -> tuple[Path, Path]:
        project, export = body.get("project"), body.get("export")
        if not isinstance(project, str) or not isinstance(export, str) or not project or not export:
            raise ValueError("укажите проект Logic и папку с экспортом")
        return Path(project).expanduser(), Path(export).expanduser()

    @app.post("/api/inspect")
    def post_inspect(body: dict = Body(...)):
        try:
            return inspect_project(*paths(body))
        except (OSError, ValueError, KeyError) as error:
            return refuse(error, 400)

    @app.post("/api/analyze")
    def post_analyze(body: dict = Body(...)):
        try:
            project, export = paths(body)
            song = body.get("song")
            if not isinstance(song, str) or not song.strip():
                raise ValueError("укажите код песни")
            ws.start(project, export, song.strip().upper())
        except BusyError as error:
            return refuse(error, 409)
        except (OSError, ValueError) as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/close")
    def post_close(body: dict | None = Body(None)):
        try:
            ws.close(discard=bool((body or {}).get("discard")))
        except (BusyError, ConfirmationError) as error:
            return refuse(error, 409)
        return current()

    @app.post("/api/edit")
    def post_edit(op: dict = Body(...)):
        if ws.session is None:
            return no_plan()
        try:
            ws.session.edit(op)
        except BusyError as error:
            return refuse(error, 409)
        except editing.EditError as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/undo")
    def post_undo():
        if ws.session is None:
            return no_plan()
        try:
            ws.session.undo()
        except BusyError as error:
            return refuse(error, 409)
        except editing.EditError as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/save")
    def post_save():
        if ws.session is None:
            return no_plan()
        try:
            ws.session.save()
        except OSError as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/confirm")
    def post_confirm():
        if ws.session is None:
            return no_plan()
        try:
            ws.session.confirm()
        except ConfirmationError as error:
            return refuse(error, 409)
        return current()

    @app.post("/api/export")
    def post_export(body: dict = Body(...)):
        if ws.session is None:
            return no_plan()
        folder, name = body.get("folder"), body.get("name")
        if not (folder is None or isinstance(folder, str)) or not (name is None or isinstance(name, str)):
            return refuse(ExportTargetError("папка и имя должны быть текстом"), 400)
        try:
            ws.session.set_target(Path(folder) if folder else None, name)
        except ExportTargetError as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/pick-folder")
    def post_pick_folder():
        if ws.session is None:
            return no_plan()
        try:
            folder = picker()
            if folder is not None:
                ws.session.set_target(folder, None)
        except ExportTargetError as error:
            return refuse(error, 400)
        return current()

    @app.post("/api/build")
    def post_build(body: dict | None = Body(None)):
        session = ws.session
        if session is None:
            return no_plan()
        try:
            if session.folder is None:
                raise ExportTargetError("выберите папку для проекта")
            if session.target()["exists"] and not (body or {}).get("overwrite"):
                return refuse(ExportTargetError("проект с таким именем уже есть: нужно подтверждение перезаписи"), 409)
            project = session.build(session.folder, session.name)
        except (BusyError, ConfirmationError) as error:
            return refuse(error, 409)
        except (OSError, ValueError) as error:
            return refuse(error, 400)
        return {"project": str(project)}

    @app.post("/api/finish")
    def post_finish(body: dict | None = Body(None)):
        session = ws.session
        if session is None:
            return no_plan()
        try:
            project = session.finish(overwrite=bool((body or {}).get("overwrite")))
        except BusyError as error:
            return refuse(error, 409)
        except ConfirmationError as error:
            return refuse(error, 400)
        except ExportTargetError as error:
            return refuse(error, 409 if "уже есть" in str(error) else 400)
        except (OSError, ValueError) as error:
            return refuse(error, 400)
        return {"project": str(project), **current()}

    @app.get("/api/project")
    def get_project():
        if ws.session is None or ws.session.built is None:
            return refuse(RuntimeError("проект ещё не собран"), 409)
        try:
            return xpj.read_overview(ws.session.built)
        except ValueError as error:
            return refuse(error, 400)

    @app.get("/api/project/audio")
    def get_project_audio(name: str):
        """Звук пэда собранного проекта: только файлы, на которые ссылаются пэды."""
        try:
            if ws.session is None or ws.session.built is None:
                raise KeyError(name)
            view = xpj.read_overview(ws.session.built)
            if name not in {p["file"] for t in view["tracks"] for p in t["pads"]}:
                raise KeyError(name)
            folder = Path(view["folder"])
            path = folder / name
            if name != Path(name).name or path.is_symlink() or not path.is_file() or path.resolve().parent != folder.resolve():
                raise KeyError(name)
        except (KeyError, ValueError, OSError):
            return refuse(KeyError("нет такого файла"), 404)
        return FileResponse(path, media_type="audio/wav")

    @app.get("/api/audio")
    def get_audio(name: str):
        try:
            if ws.session is None:
                raise KeyError(name)
            path = ws.session.audio(name)
        except KeyError:
            return refuse(KeyError("нет такого куска"), 404)
        return FileResponse(path, media_type="audio/wav")

    return app


def serve(session: Session | None, out: Path | None, name: str | None, port: int, open_browser: bool = True) -> None:
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=[f"http://{HOST}:{port}/"]).start()
    uvicorn.run(create_app(session, out, name), host=HOST, port=port, log_level="warning")
