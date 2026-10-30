#!/usr/bin/env python3
"""Разведка проекта MPC для спайка 4. Только чтение, не код продукта.

    xpj_inspect.py summary <project.xpj>
    xpj_inspect.py path <project.xpj> <путь.через.точки> [--depth 2]
    xpj_inspect.py diff <a.xpj> <b.xpj>
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

HEADER_LINES = 5


def load(path: Path) -> tuple[list[str], dict[str, Any]]:
    data = gzip.decompress(path.read_bytes())
    parts = data.split(b"\n", HEADER_LINES)
    header = [line.decode("ascii") for line in parts[:HEADER_LINES]]
    return header, json.loads(parts[HEADER_LINES])["data"]


def get(node: Any, path: str) -> Any:
    for part in path.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def brief(node: Any, depth: int, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (dict, list)) and depth > 0:
                print(f"{pad}{key}: {type(value).__name__}[{len(value)}]")
                brief(value, depth - 1, indent + 1)
            else:
                print(f"{pad}{key}: {str(value)[:70]}")
    elif isinstance(node, list):
        for number, value in enumerate(node[:6]):
            print(f"{pad}[{number}]")
            brief(value, depth - 1, indent + 1)
        if len(node) > 6:
            print(f"{pad}… ещё {len(node) - 6}")
    else:
        print(f"{pad}{str(node)[:70]}")


def clip_stats(project: dict[str, Any]) -> Counter[str]:
    """Сколько событий каких типов у каждого трека по всем секвенциям."""
    notes: Counter[str] = Counter()
    for sequence in project["sequences"]:
        for clips in sequence["value"]["trackClipMaps"]:
            for clip in clips:
                for event in clip["value"]["eventList"]["events"]:
                    kind = "note" if "note" in event else f"type{event.get('type')}"
                    notes[f"{clip['key']}: {kind}"] += 1
    return notes


def cmd_summary(args: argparse.Namespace) -> None:
    header, project = load(args.project)
    print(f"заголовок: {header}")
    print(f"версия данных {project['version']}, темп {project['masterTempo']}")
    print(f"создан {project['originalCreatorProductIdentifier']}, сохранён {project['lastSavedProductIdentifier']}")
    print(f"сэмплов {len(project['samples'])}, треков {len(project['tracks'])}")
    for number, track in enumerate(project["tracks"]):
        program = track.get("program") or {}
        output = track["midiOutputRoute"]
        port = output["outputPort"]["deviceName"]
        print(
            f"{number:2d} {track['name']}: тип {program.get('type')}, "
            f"сэмплов {len(program.get('samples', []))}, выход {port}/{output['outputChannel']}, "
            f"ключи {sorted(set(program) & {'drum', 'keygroup', 'plugin', 'midi', 'cv', 'audio'})}"
        )
    for sequence in project["sequences"]:
        value = sequence["value"]
        print(f"секвенция {sequence['key']} {value['name']}: {value['bpm']} BPM, тактов {value['lengthBars']}")
    for key, count in sorted(clip_stats(project).items()):
        print(f"  {key}: {count}")


def flatten(node: Any, path: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = enumerate(node)
    else:
        return {path: node}
    result: dict[str, Any] = {}
    for key, value in items:
        result.update(flatten(value, f"{path}.{key}" if path else str(key)))
    return result


def cmd_diff(args: argparse.Namespace) -> None:
    left = flatten(load(args.a)[1])
    right = flatten(load(args.b)[1])
    changed = sorted(key for key in left.keys() | right.keys() if left.get(key) != right.get(key))
    print(f"изменилось полей: {len(changed)}")
    for key in changed[: args.limit]:
        print(f"{key}: {str(left.get(key))[:40]} → {str(right.get(key))[:40]}")


def cmd_path(args: argparse.Namespace) -> None:
    brief(get(load(args.project)[1], args.path), args.depth)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("project", type=Path)
    summary.set_defaults(run=cmd_summary)
    path = commands.add_parser("path")
    path.add_argument("project", type=Path)
    path.add_argument("path")
    path.add_argument("--depth", type=int, default=2)
    path.set_defaults(run=cmd_path)
    diff = commands.add_parser("diff")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.add_argument("--limit", type=int, default=100)
    diff.set_defaults(run=cmd_diff)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
