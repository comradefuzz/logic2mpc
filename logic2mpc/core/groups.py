"""Группы и код песни по умолчанию, AN-071."""
from __future__ import annotations

from .names import transliterate

OTHER = "Прочее"
OTHER_CODE = "OT"
STEMS = (
    ("drum", "DR"), ("bass", "BS"), ("synth", "SY"), ("lead", "SY"), ("key", "SY"),
    ("fx", "FX"), ("vocal", "VX"), ("vox", "VX"), ("guitar", "GT"),
)


def latin_letters(text: str) -> list[str]:
    return [c for c in transliterate(text) if c.isascii() and c.isalpha()]


def group_code(name: str) -> str:
    if name == OTHER:
        return OTHER_CODE
    lowered = transliterate(name).lower()
    for stem, code in STEMS:
        if lowered.startswith(stem):
            return code
    return "".join(latin_letters(name)[:2]).upper().ljust(2, "X")


def default_groups(names: list[str]) -> dict[str, dict[str, str]]:
    return {name: {"code": group_code(name), "method": "drum"} for name in names}


def song_code(project_name: str) -> str:
    part = project_name.split(" - ", 1)[1] if " - " in project_name else project_name
    letters = latin_letters(part)
    return "".join(letters[:3]).upper().ljust(3, "X") if letters else "SNG"
