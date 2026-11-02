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

from ..app import BusyError, ConfirmationError, ExportTargetError, Session
from ..core import edit as editing
from ..core import report
from ..core.plan import is_exported, to_json

HOST = "127.0.0.1"
PAGE = Path(__file__).resolve().parent.parent / "web" / "index.html"


def state(session: Session) -> dict:
    pads = {g.name: sum(is_exported(p) for t in g.tracks for p in t.pieces) for g in session.plan.groups}
    return {
        "version": session.version.name,
        "dirty": session.dirty,
        "confirmed": session.confirmed,
        "busy": session.busy,
        "plan": json.loads(to_json(session.plan)),
        "pads": pads,
        "export": session.target(),
    }


def pick_folder() -> Path | None:
    """Системное окно выбора папки macOS. Браузер полного пути не отдаёт, окно открывает сервер."""
    script = 'POSIX path of (choose folder with prompt "Папка для проекта MPC")'
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    except OSError as error:
        raise ExportTargetError(f"окно выбора папки недоступно: {error}") from None
    text = result.stdout.strip()
    return Path(text) if result.returncode == 0 and text else None


def create_app(session: Session, out: Path | None, name: str | None, picker=pick_folder) -> FastAPI:
    app = FastAPI()
    if out is not None or name is not None:
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

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/state")
    def get_state() -> dict:
        return state(session)

    @app.get("/api/report", response_class=PlainTextResponse)
    def get_report() -> str:
        return report.render(session.plan)

    @app.post("/api/edit")
    def post_edit(op: dict = Body(...)):
        try:
            session.edit(op)
        except BusyError as error:
            return refuse(error, 409)
        except editing.EditError as error:
            return refuse(error, 400)
        return state(session)

    @app.post("/api/undo")
    def post_undo():
        try:
            session.undo()
        except BusyError as error:
            return refuse(error, 409)
        except editing.EditError as error:
            return refuse(error, 400)
        return state(session)

    @app.post("/api/save")
    def post_save():
        try:
            session.save()
        except OSError as error:
            return refuse(error, 400)
        return state(session)

    @app.post("/api/confirm")
    def post_confirm():
        try:
            session.confirm()
        except ConfirmationError as error:
            return refuse(error, 409)
        return state(session)

    @app.post("/api/export")
    def post_export(body: dict = Body(...)):
        folder, name = body.get("folder"), body.get("name")
        if not (folder is None or isinstance(folder, str)) or not (name is None or isinstance(name, str)):
            return refuse(ExportTargetError("папка и имя должны быть текстом"), 400)
        try:
            session.set_target(Path(folder) if folder else None, name)
        except ExportTargetError as error:
            return refuse(error, 400)
        return state(session)

    @app.post("/api/pick-folder")
    def post_pick_folder():
        try:
            folder = picker()
            if folder is not None:
                session.set_target(folder, None)
        except ExportTargetError as error:
            return refuse(error, 400)
        return state(session)

    @app.post("/api/build")
    def post_build(body: dict | None = Body(None)):
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
        return {"project": str(project), **state(session)}

    @app.get("/api/audio")
    def get_audio(name: str):
        try:
            path = session.audio(name)
        except KeyError:
            return refuse(KeyError("нет такого куска"), 404)
        return FileResponse(path, media_type="audio/wav")

    return app


def serve(session: Session, out: Path | None, name: str | None, port: int, open_browser: bool = True) -> None:
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=[f"http://{HOST}:{port}/"]).start()
    uvicorn.run(create_app(session, out, name), host=HOST, port=port, log_level="warning")
