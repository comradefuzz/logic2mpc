"""Проверка реестра тестов (`scripts/tests_registry.py`)."""
from __future__ import annotations

from pathlib import Path

import pytest

import tests_registry as registry

HEADER = "\t".join(registry.COLUMNS)


def write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[str], collected: list[str]) -> None:
    path = tmp_path / "registry.tsv"
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(registry, "REGISTRY", path)
    monkeypatch.setattr(registry, "collect", lambda: collected)
    monkeypatch.setattr(registry, "ROOT", tmp_path)


def row(test: str, status: str = "active", removed: str = "", purpose: str = "суть") -> str:
    return "\t".join([test, purpose, "причина", status, removed])


def test_real_registry_matches_the_suite() -> None:
    assert registry.check() == []


def test_missing_and_stale_rows_are_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, monkeypatch, [row("tests/a.py::test_old")], ["tests/a.py::test_new"])
    errors = "\n".join(registry.check())
    assert "test_new: тест есть в наборе, но не внесён" in errors and "test_old: в реестре active, но в наборе нет" in errors


def test_removed_row_needs_a_reason_and_active_row_a_purpose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, monkeypatch, [row("tests/a.py::test_x", "removed"), row("tests/a.py::test_y", purpose="")], ["tests/a.py::test_y"])
    errors = "\n".join(registry.check())
    assert "удалённый тест без причины удаления" in errors and "пустое поле purpose" in errors


def test_spike_and_story_tests_are_forbidden_in_the_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, monkeypatch, [row("spikes/x/test_a.py::test_a"), row("story_tests/S-001/test_b.py::test_b")], [])
    errors = "\n".join(registry.check())
    assert errors.count("не входят") == 2


def test_spike_test_files_are_forbidden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, monkeypatch, [], [])
    (tmp_path / "spikes" / "s").mkdir(parents=True)
    (tmp_path / "spikes" / "s" / "test_a.py").write_text("")
    assert any("тесты спайков запрещены" in e for e in registry.check())
