"""Инструмент сравнения адаптеров scripts/adapter_overlap.py на синтетических модулях."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapter_overlap as ao  # noqa: E402

A = '''
"""Адаптер A."""
VERSIONS = (1,)

def same(x):
    """Док."""
    # комментарий
    return x + 1

def changed(x):
    return x * 2

def only_a(x):
    return -x

class K:
    def method(self):
        return 1
'''

B = '''
"""Адаптер B, другой докстринг."""
VERSIONS = (2,)

def same(x):
    """Другой док."""
    return x + 1   # другой комментарий

def changed(x):
    return x * 3

def only_b(x):
    return x

class K:
    def method(self):
        return 1
'''


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_overlap_counts(tmp_path: Path) -> None:
    result = ao.compare(write(tmp_path, "a.py", A), write(tmp_path, "b.py", B))
    assert result["identical"] == ["K.method", "same"]
    assert result["changed"] == ["changed"]
    assert result["only_a"] == ["only_a"] and result["only_b"] == ["only_b"]
    assert result["total_a"] == 4 and result["total_b"] == 4
    assert result["ratio"] == 0.5


def test_identical_modules(tmp_path: Path) -> None:
    result = ao.compare(write(tmp_path, "a.py", A), write(tmp_path, "c.py", A))
    assert result["ratio"] == 1.0 and not result["changed"] and not result["only_a"]


def test_disjoint_modules(tmp_path: Path) -> None:
    other = write(tmp_path, "d.py", "def zzz():\n    return 0\n")
    result = ao.compare(write(tmp_path, "a.py", A), other)
    assert result["ratio"] == 0.0


def test_report_text(tmp_path: Path) -> None:
    text = ao.report(ao.compare(write(tmp_path, "a.py", A), write(tmp_path, "b.py", B)))
    assert "50%" in text and "changed" in text
