"""Выбор адаптера Logic по версии файла ProjectData активной альтернативы.

Правило «адаптер на версию формата» (CLAUDE.md): проверенный адаптер не правится, новая версия получает новый.
Неизвестная версия даёт отказ, а не догадку.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType

from . import logic, logic12
from .logic import MAGIC, Song, alternative, u16

ADAPTERS: tuple[ModuleType, ...] = (logic, logic12)


def file_version(project: Path) -> int:
    """Версия файла ProjectData активной альтернативы (`+0x04`)."""
    data = (alternative(project) / "ProjectData").read_bytes()[:6]
    if len(data) < 6:
        raise ValueError(f"ProjectData короче заголовка: {len(data)} байт")
    if data[:4] != MAGIC:
        raise ValueError(f"нет сигнатуры ProjectData: {data[:4].hex()}")
    return u16(data, 4)


def known_versions() -> list[int]:
    return sorted(v for module in ADAPTERS for v in module.VERSIONS)


def read_project(project: Path) -> Song:
    version = file_version(project)
    for module in ADAPTERS:
        if version in module.VERSIONS:
            return module.read_project(project)
    known = ", ".join(f"{v:#06x}" for v in known_versions())
    raise ValueError(f"версия файла проекта {version:#06x} не поддерживается, известны: {known}")


__all__ = ["ADAPTERS", "file_version", "known_versions", "read_project"]
