"""Выбор адаптера Logic по версии файла и адаптер Logic 12 (S-028)."""
from __future__ import annotations

import plistlib
import struct
from pathlib import Path

import pytest

from logic2mpc.adapters import logic, logic12, logic_source

MAGIC = bytes.fromhex("2347c0ab")


def project_file(version: int, body: bytes = b"") -> bytes:
    """Заголовок ProjectData: сигнатура, версия, остаток до 24 байт, длина записей."""
    head = MAGIC + struct.pack("<H", version) + bytes(10) + struct.pack("<I", len(body)) + bytes(4)
    return head + body


def make_project(tmp_path: Path, versions: dict[str, int], active: int | None = None) -> Path:
    root = tmp_path / "P.logicx"
    for number, version in versions.items():
        alt = root / "Alternatives" / number
        alt.mkdir(parents=True)
        (alt / "ProjectData").write_bytes(project_file(version))
    (root / "Resources").mkdir()
    info = {} if active is None else {"ActiveVariant": active}
    (root / "Resources/ProjectInformation.plist").write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    return root


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logic, "read_project", lambda p: "old")
    monkeypatch.setattr(logic12, "read_project", lambda p: "new")


def test_versions_declared() -> None:
    assert logic.VERSIONS == (0x09CB,)
    assert logic12.VERSIONS == (0x09D1,)


def test_adapters_have_same_interface() -> None:
    for name in ("Song", "Record", "walk", "alternative", "read_project", "u16", "u32"):
        assert hasattr(logic12, name), name


def test_dispatch_by_version(tmp_path: Path, fakes: None) -> None:
    assert logic_source.read_project(make_project(tmp_path / "a", {"000": 0x09CB})) == "old"
    assert logic_source.read_project(make_project(tmp_path / "b", {"000": 0x09D1})) == "new"


def test_mixed_package_uses_active_alternative(tmp_path: Path, fakes: None) -> None:
    project = make_project(tmp_path, {"000": 0x09D1, "001": 0x09CB}, active=0)
    assert logic_source.read_project(project) == "new"
    other = make_project(tmp_path / "x", {"000": 0x09D1, "001": 0x09CB}, active=1)
    assert logic_source.read_project(other) == "old"


def test_without_active_variant_last_alternative(tmp_path: Path, fakes: None) -> None:
    project = make_project(tmp_path, {"000": 0x09CB, "001": 0x09D1})
    assert logic_source.read_project(project) == "new"


def test_unknown_version_refused_with_versions_in_message(tmp_path: Path, fakes: None) -> None:
    with pytest.raises(ValueError) as error:
        logic_source.read_project(make_project(tmp_path, {"000": 0x09FF}))
    text = str(error.value)
    assert "0x09ff" in text.lower() and "0x09cb" in text.lower() and "0x09d1" in text.lower()


def test_no_signature_refused(tmp_path: Path, fakes: None) -> None:
    project = make_project(tmp_path, {"000": 0x09CB})
    (project / "Alternatives/000/ProjectData").write_bytes(b"\x00" * 64)
    with pytest.raises(ValueError, match="сигнатур"):
        logic_source.read_project(project)


def test_truncated_file_refused(tmp_path: Path, fakes: None) -> None:
    project = make_project(tmp_path, {"000": 0x09CB})
    (project / "Alternatives/000/ProjectData").write_bytes(MAGIC)
    with pytest.raises(ValueError):
        logic_source.read_project(project)


def test_no_projectdata_refused(tmp_path: Path, fakes: None) -> None:
    root = tmp_path / "E.logicx"
    (root / "Alternatives").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        logic_source.read_project(root)


def test_adapters_do_not_cover_each_other() -> None:
    old, new = project_file(0x09CB), project_file(0x09D1)
    assert logic.walk(old) == [] and logic12.walk(new) == []
    with pytest.raises(ValueError, match="версия"):
        logic12.walk(old)
    with pytest.raises(ValueError, match="версия"):
        logic.walk(new)


def test_old_adapter_untouched() -> None:
    """Адаптер 10.8.1 заморожен (CLAUDE.md): известная версия и отказ на 0x09D1 те же, что до S-028."""
    assert 0x09D1 not in logic.VERSIONS
