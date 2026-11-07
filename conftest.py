"""Области общего набора (docs/testing.md): build, web, core, tools. У каждого теста ровно одна.

Область файла задана здесь по умолчанию, отдельный тест переопределяет её своей меткой (`@pytest.mark.web`).
Файл без области и без метки на тесте это ошибка сбора: новый файл тестов надо отнести к области.
"""
from __future__ import annotations

import pytest

AREAS = ("build", "web", "core", "tools")
DEFAULT_AREA = {
    "tests/test_xpj_spec.py": "build",
    "tests/test_export.py": "build",
    "tests/test_mpcfile.py": "build",
    "tests/test_overview.py": "build",
    "tests/test_analysis.py": "core",
    "tests/test_edit.py": "core",
    "tests/test_groups.py": "core",
    "tests/test_real_project.py": "core",
    "tests/test_session.py": "core",
    "tests/test_start.py": "core",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = item.nodeid.split("::")[0]
        own = [m.name for m in item.own_markers if m.name in AREAS]
        if len(own) > 1:
            raise pytest.UsageError(f"{item.nodeid}: больше одной области {own}")
        if not own:
            area = "tools" if path.startswith("scripts/") else DEFAULT_AREA.get(path)
            if area is None:
                raise pytest.UsageError(f"{item.nodeid}: файл {path} не отнесён к области, добавьте его в conftest.py")
            item.add_marker(getattr(pytest.mark, area))
