#!/usr/bin/env python3
"""Прогон сценариев S-009 на экспорте Elated 1. Папки для ревью пишутся рядом с экспортом в review/."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402
import decide  # noqa: E402

PROJECT = ROOT / "test-projects/copies/Fuzz - Elated.logicx"
EXPORT = ROOT / "test-projects/exports/elated"
OUT = EXPORT / "review"
SCENARIOS = [
    ("02_LD Saw Harm.wav", "LD Saw Harm", "SY", "LDSawHarm"),
    ("23_Fill JaBouncy.wav", "Fill JaBouncy", "DR", "FillJaBouncy"),
    ("03_SY - Fire Glow.wav", "SY - Fire Glow", "SY", "FireGlow"),
    ("17_HH Meat.wav", "HH Meat", "DR", "HHMeat"),
]
VALUES = (0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 1.0)


def main() -> None:
    write = "--write" in sys.argv
    print("дорожка | длина | " + " | ".join(str(v) for v in VALUES) + " | по умолчанию: вердикт, уверенность, покрытие")
    for wav, track, group, name in SCENARIOS:
        text = subprocess.run(
            [sys.executable, ROOT / "spikes/logic_read/probe.py", "positions", PROJECT, "--track", track],
            check=True, capture_output=True, text=True,
        ).stdout
        OUT.mkdir(exist_ok=True)
        grid_path = OUT / f"{name}.grid.json"
        grid_path.write_text(text, encoding="utf-8")
        audio, sr = sf.read(EXPORT / wav, always_2d=True)
        measured = decide.measure(audio, sr, analyze.load_grid(grid_path))
        counts = [len(decide.cut(measured, value).groups) for value in VALUES]
        result = decide.cut(measured, decide.DEFAULT)
        print(
            f"{track} | {result.window_bars} | " + " | ".join(map(str, counts))
            + f" | {result.verdict}, {result.confidence}, {result.coverage}",
            flush=True,
        )
        if write:
            print(decide.write_version(OUT / name, audio, sr, result, "ELA", group, name))


if __name__ == "__main__":
    main()
