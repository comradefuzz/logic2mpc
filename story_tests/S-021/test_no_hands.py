"""S-021: экспорт без пустого трека HANDS. Тесты стори, в общий набор переносятся при приёмке по разделу «Тестирование»."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from logic2mpc.adapters import xpj  # noqa: E402
from logic2mpc.core.plan import Group  # noqa: E402
from test_export import sample_plan, write_samples  # noqa: E402


def built(tmp_path: Path, plan=None) -> dict:
    plan = plan or sample_plan()
    write_samples(plan, tmp_path / "samples")
    return xpj.load(xpj.write_project(plan, tmp_path / "samples", tmp_path / "out", "Song")).data


def test_group_named_hands_is_allowed(tmp_path: Path) -> None:
    plan = sample_plan()
    plan.groups[0] = Group("HANDS", "DR", "drum", plan.groups[0].tracks)
    data = built(tmp_path, plan)
    assert [t["name"] for t in data["tracks"] if t["program"]["type"] < 7] == ["HANDS", "Bass"]


def test_build_is_deterministic(tmp_path: Path) -> None:
    plan = sample_plan()
    write_samples(plan, tmp_path / "samples")
    one = xpj.write_project(plan, tmp_path / "samples", tmp_path / "a", "Song").read_bytes()
    two = xpj.write_project(plan, tmp_path / "samples", tmp_path / "b", "Song").read_bytes()
    assert one == two
