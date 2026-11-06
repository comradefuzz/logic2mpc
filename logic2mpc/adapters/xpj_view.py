"""Просмотр собранного `.xpj`: сводка по файлу и папке `<имя>_[ProjectData]`. Не часть сборки, контракта экспортёра не касается."""
from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any

from ..core.overview import summarize
from .mpcfile import load


def read_overview(project: Path) -> dict[str, Any]:
    """Сводка собранного `.xpj` и папки `<имя>_[ProjectData]`: треки с пэдами, секвенции, сэмплы, размеры."""
    if not project.is_file():
        raise ValueError(f"нет проекта {project}")
    folder = project.parent / f"{project.stem}_[ProjectData]"
    try:
        files = {p.name: p.stat().st_size for p in folder.iterdir() if p.is_file() and not p.name.startswith("._")} if folder.is_dir() else {}
        view = summarize(load(project).data, files)
    except (OSError, ValueError, KeyError, TypeError, IndexError, EOFError, zlib.error) as error:
        raise ValueError(f"не удалось прочитать проект {project.name}: {error.__class__.__name__}") from None
    samples = sum(files.values())
    try:
        size = project.stat().st_size
    except OSError as error:
        raise ValueError(f"не удалось прочитать проект {project.name}: {error.__class__.__name__}") from None
    return {
        "project": str(project), "folder": str(folder), **view,
        "size": {"project": size, "samples": samples, "total": size + samples},
    }
