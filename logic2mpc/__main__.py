"""Команды:

    python -m logic2mpc analyze <project.logicx> <export> --groups <groups.json> --out <папка>
    python -m logic2mpc confirm <папка версии>
    python -m logic2mpc build <папка версии> --out <папка> --name <имя проекта>
    python -m logic2mpc ui [<папка плана или версии>] [--out <папка>] [--name <имя проекта>] [--port N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import app
from .core.windows import DEFAULT


def main() -> int:
    parser = argparse.ArgumentParser(prog="logic2mpc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("project", type=Path)
    analyze.add_argument("export", type=Path)
    analyze.add_argument("--groups", type=Path, required=True)
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--decisiveness", type=float, default=DEFAULT)
    confirm = commands.add_parser("confirm")
    confirm.add_argument("version", type=Path)
    build = commands.add_parser("build")
    build.add_argument("version", type=Path)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--name", required=True)
    ui = commands.add_parser("ui")
    ui.add_argument("version", type=Path, nargs="?")
    ui.add_argument("--out", type=Path)
    ui.add_argument("--name")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            def show(done: int, total: int, track: str) -> None:
                if track:
                    print(f"[{done + 1}/{total}] {track}", flush=True)

            print(app.analyze(args.project, args.export, args.groups, args.out, args.decisiveness, show))
        elif args.command == "ui":
            from .adapters import web

            if args.out:
                args.out.mkdir(parents=True, exist_ok=True)
            version = app.find_version(args.version) if args.version else None
            if args.version and version is None:
                raise ValueError(f"в {args.version} нет плана: нужна папка версии или папка с версиями vN")
            web.serve(app.Session(version) if version else None, args.out, args.name, args.port, not args.no_browser)
        elif args.command == "confirm":
            print(app.confirm(args.version))
        else:
            print(app.build(args.version, args.out, args.name))
    except (app.ConfirmationError, FileNotFoundError, ValueError) as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
