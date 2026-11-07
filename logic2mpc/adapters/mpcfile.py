"""Контейнер проекта MPC: gzip, заголовок из пяти строк, JSON с числами в исходной записи.

Числа хранятся как текст: Live 2 пишет float с 17 знаками, и обычный json их округлит.
"""
from __future__ import annotations

import gzip
import json
from json.encoder import encode_basestring
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HEADER_LINES = 5


class Number(str):
    """Число JSON в исходной записи."""


@dataclass
class Project:
    header: bytes
    data: dict[str, Any]


def parse(raw: bytes) -> Project:
    parts = raw.split(b"\n", HEADER_LINES)
    header = b"\n".join(parts[:HEADER_LINES]) + b"\n"
    root = json.loads(parts[HEADER_LINES], parse_float=Number)
    return Project(header, root["data"])


def load(path: Path) -> Project:
    return parse(gzip.decompress(path.read_bytes()))


def dump(node: Any) -> str:
    """Запись JSON в раскладке Live 2: каждый элемент на своей строке. Быстрые ветки для частых типов."""
    kind = type(node)
    if kind is str:
        return encode_basestring(node)
    if kind is int:
        return str(node)
    if kind is bool:
        return "true" if node else "false"
    if node is None:
        return "null"
    if kind is Number:
        return str(node)
    if kind is dict:
        if not node:
            return "{}"
        return "{\n" + ",\n".join([f"{encode_basestring(k)}: {dump(v)}" for k, v in node.items()]) + "\n}"
    if kind is list:
        if not node:
            return "[]"
        return "[\n" + ",\n".join([dump(v) for v in node]) + "\n]"
    if isinstance(node, Number):
        return str(node)
    return json.dumps(node, ensure_ascii=False)


def render(project: Project) -> bytes:
    return project.header + dump({"data": project.data}).encode("utf-8")


def pack(raw: bytes) -> bytes:
    data = bytearray(gzip.compress(raw, mtime=0))
    data[8] = 0  # заголовок как у файлов с Live 2
    data[9] = 3
    return bytes(data)
