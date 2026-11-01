"""Команды:

    python -m logic2mpc analyze <project.logicx> <export> --groups <groups.json> --out <папка>
    python -m logic2mpc confirm <папка версии>
    python -m logic2mpc build <папка версии> --out <папка> --name <имя проекта>
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
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            print(app.analyze(args.project, args.export, args.groups, args.out, args.decisiveness))
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
