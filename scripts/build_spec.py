#!/usr/bin/env python3
"""Собирает описание формата MPC для экспорта: `logic2mpc/spec/*.json` по `export.tsv` и эталонам.

    build_spec.py [--out DIR]

Описание это объекты, которые создаёт экспорт, без полей `required = no` из `docs/formats/mpc/export.tsv`.
Эталоны (`test-projects`) нужны только этому скрипту, в пакет они не входят: `Empty.xpj` даёт корень, драм-трек и пэд,
`D01 pads16` секвенцию, клип, событие и запись сэмпла.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logic2mpc.adapters import mpcfile  # noqa: E402

EXPORT = ROOT / "docs" / "formats" / "mpc" / "export.tsv"
EMPTY = ROOT / "test-projects" / "reference" / "Empty.xpj"
PADS16 = ROOT / "test-projects" / "mpc" / "spike7" / "D01 pads16.xpj"
OUT = ROOT / "logic2mpc" / "spec"
ROOT_KEEP = (
    "version", "key", "masterTempoEnabled", "masterTempo", "samples", "tracks", "sequences",
    "currentTrackIndex", "currentSequence", "engineMode",
)
CLIP = "data.sequences[].value.trackClipMaps[][].value"
PREFIX = {
    "track": "data.tracks[]",
    "pad": "data.tracks[].program.drum.instruments[]",
    "sequence": "data.sequences[].value",
    "clip": CLIP,
    "event": f"{CLIP}.eventList.events[]",
    "sample": "data.samples[]",
    "program_sample": "data.tracks[].program.samples[]",
}
SAMPLE_KEY = "C Major"


def registry_no() -> set[str]:
    lines = [x.split("\t") for x in EXPORT.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return {cells[0] for cells in lines[1:] if len(cells) > 3 and cells[3] == "no"}


def prune(node: Any, path: str, no: set[str]) -> Any:
    """Убирает поля, помеченные в реестре как необязательные. Путь как в `schema.tsv`."""
    if isinstance(node, dict):
        return {k: prune(v, f"{path}.{k}", no) for k, v in node.items() if f"{path}.{k}" not in no}
    if isinstance(node, list):
        return [prune(item, f"{path}[]", no) for item in node]
    return node


def first_note(data: dict[str, Any]) -> dict[str, Any]:
    for sequence in data["sequences"]:
        for row in sequence["value"]["trackClipMaps"]:
            for clip in row:
                for event in clip["value"]["eventList"]["events"]:
                    if "note" in event:
                        return event
    raise ValueError("в эталоне нет ноты")


def build() -> tuple[dict[str, str], bytes]:
    no = registry_no()
    empty, pads = mpcfile.load(EMPTY), mpcfile.load(PADS16)
    track = copy.deepcopy(empty.data["tracks"][0])
    pad = copy.deepcopy(track["program"]["drum"]["instruments"][0])
    track["program"]["drum"]["instruments"] = []
    track["program"]["samples"] = []
    sequence = copy.deepcopy(pads.data["sequences"][0]["value"])
    clip = copy.deepcopy(sequence["trackClipMaps"][0][0]["value"])
    clip["eventList"]["events"] = []
    event = copy.deepcopy(first_note(pads.data))
    sequence["trackClipMaps"] = [[]]
    sample = copy.deepcopy(pads.data["samples"][0])
    sample["metadata"]["key"] = SAMPLE_KEY
    root = {k: copy.deepcopy(empty.data[k]) for k in ROOT_KEEP}
    root["samples"], root["tracks"], root["sequences"] = [], [], []
    objects = {
        "track": track, "pad": pad, "sequence": sequence, "clip": clip, "event": event, "sample": sample,
        "program_sample": copy.deepcopy(sample),
    }
    files = {f"{name}.json": mpcfile.dump(prune(node, PREFIX[name], no)) + "\n" for name, node in objects.items()}
    files["root.json"] = mpcfile.dump(root) + "\n"
    return files, empty.header


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    files, header = build()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8")
    (args.out / "header.txt").write_bytes(header)
    print(f"{args.out}: {len(files) + 1} файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
