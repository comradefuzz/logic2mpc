"""S-028: чтение Logic 12 равно чтению 10.8.1 на общих эталонах. Нужен test-projects (не в git), иначе пропуск."""
from __future__ import annotations

from pathlib import Path

import pytest

from logic2mpc.adapters import logic, logic12

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "test-projects/reference/L12/Spike Control copy.logicx/Alternatives/000"
OLD = ROOT / "test-projects/Spike Control.logicx/Alternatives/000"
pytestmark = pytest.mark.skipif(not (NEW.exists() and OLD.exists()), reason="нет test-projects")


def read(module, alt: Path) -> dict:
    records = module.walk((alt / "ProjectData").read_bytes())
    midi, extended, outside = module.midi_regions(records)
    return {
        "tempo": module.tempo_map(records),
        "meter": module.meter_map(records),
        "markers": module.markers(records),
        "rows": [(r.number, r.name, r.depth, r.header) for r in module.rows_of(records)],
        "audio": module.audio_regions(records, 100.0, 48000),
        "midi": midi,
        "counts": (extended, outside),
    }


def test_same_reading_each_adapter_own_version() -> None:
    assert read(logic12, NEW) == read(logic, OLD)


def test_logic12_adapter_reads_new_not_old() -> None:
    with pytest.raises(ValueError):
        logic12.walk((OLD / "ProjectData").read_bytes())
    with pytest.raises(ValueError):
        logic.walk((NEW / "ProjectData").read_bytes())


def test_dispatch_on_real_packages() -> None:
    """Spike Control отклоняется ограничением постоянного темпа, и это отказ адаптера своей версии, не выбора."""
    from logic2mpc.adapters import logic_source

    for project in (NEW.parents[1], OLD.parents[1]):
        with pytest.raises(ValueError, match="постоянный темп"):
            logic_source.read_project(project)
