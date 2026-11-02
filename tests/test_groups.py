"""AN-071: группы и код песни по умолчанию."""
from __future__ import annotations

import pytest

from logic2mpc.core.groups import OTHER, default_groups, song_code


@pytest.mark.parametrize("name, code", [
    ("Drums", "DR"), ("drums", "DR"), ("Bass", "BS"), ("Bass 2", "BS"), ("Synth", "SY"), ("Lead", "SY"),
    ("Keys", "SY"), ("FX", "FX"), ("fx", "FX"), ("Vocals", "VX"), ("Vox", "VX"), ("Guitars", "GT"),
])
def test_an071_known_names_get_table_code(name: str, code: str) -> None:
    assert default_groups([name])[name]["code"] == code


@pytest.mark.parametrize("name, code", [
    ("Strings", "ST"), ("Pads", "PA"), ("A", "AX"), ("808", "XX"), ("Бас", "BA"), ("Перкуссия", "PE"),
])
def test_an071_other_names_get_two_latin_letters(name: str, code: str) -> None:
    assert default_groups([name])[name]["code"] == code


def test_an071_method_is_drum_and_all_names_are_kept() -> None:
    groups = default_groups(["Drums", "Strings"])
    assert list(groups) == ["Drums", "Strings"]
    assert all(g["method"] == "drum" for g in groups.values())


def test_an071_other_group_has_fixed_code() -> None:
    assert OTHER == "Прочее"
    assert default_groups([OTHER])[OTHER]["code"] == "OT"


@pytest.mark.parametrize("name, code", [
    ("Fuzz - Elated", "ELA"), ("Fuzz - Pyro", "PYR"), ("MONTERO", "MON"), ("Elated", "ELA"),
    ("Ab", "ABX"), ("Песня", "PES"), ("Fuzz - 12 Days", "DAY"), ("", "SNG"),
])
def test_an071_song_code_from_project_name(name: str, code: str) -> None:
    assert song_code(name) == code
