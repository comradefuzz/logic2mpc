"""Сводка собранного проекта MPC: что реально лежит на пэдах. Чистая функция, файлы читает адаптер."""
from __future__ import annotations

from typing import Any

KINDS = {0: "drum", 1: "keygroup", 3: "plugin", 4: "midi", 6: "audio"}
SERVICE = {7, 8, 9}
BANK = 16
BANKS = "ABCDEFGH"


def pad_view(pad: int, instrument: dict[str, Any], note: Any, files: dict[str, int]) -> dict[str, Any] | None:
    layer = instrument["layersv"][0]
    if not layer["sampleFile"]:
        return None
    return {
        "pad": pad,
        "bank": BANKS[pad // BANK],
        "number": pad % BANK + 1,
        "note": note,
        "sample": layer["sampleName"],
        "file": layer["sampleFile"],
        "exists": layer["sampleFile"] in files,
    }


def track_view(track: dict[str, Any], files: dict[str, int]) -> dict[str, Any] | None:
    program = track["program"]
    kind = KINDS.get(program["type"])
    if program["type"] in SERVICE:
        return None
    pads: list[dict[str, Any]] = []
    if kind == "drum":
        notes = program["padNoteMap"]["noteForPad"]
        for pad, instrument in enumerate(program["drum"]["instruments"][: BANK * len(BANKS)]):
            view = pad_view(pad, instrument, notes.get(f"value{pad}"), files)
            if view:
                pads.append(view)
    return {"name": track["name"], "kind": kind or f"type {program['type']}", "filled": len(pads), "pads": pads}


def summarize(data: dict[str, Any], files: dict[str, int]) -> dict[str, Any]:
    """`files`: имя файла в папке данных и его размер. Музыкальные треки, секвенции, нехватка и лишние файлы."""
    tracks = [v for t in data["tracks"] if (v := track_view(t, files))]
    used = {p["file"] for t in tracks for p in t["pads"]}
    sequences = [{"name": s["value"]["name"], "bars": s["value"]["lengthBars"]} for s in sorted(data["sequences"], key=lambda s: s["key"])]
    return {
        "tracks": tracks,
        "sequences": sequences,
        "samples": len(used),
        "missing": sorted(used - set(files)),
        "extra": sorted(set(files) - used),
    }
