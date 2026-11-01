#!/usr/bin/env python3
"""Прогон сценариев S-008 на экспорте Elated 1. Результаты пишутся рядом с экспортом в analysis/."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

PROJECT = ROOT / "test-projects/copies/Fuzz - Elated 1.logicx"
EXPORT = ROOT / "test-projects/exports/elated"
OUT = EXPORT / "analysis"
SCENARIOS = [
    (1, "14_DS_LENNO_drum_snare_package.wav", "DS_LENNO_drum_snare_package"),
    (2, "12_DS_LENNO_drum_kick_nerve.wav", "DS_LENNO_drum_kick_nerve"),
    (3, "16_Audio 48.wav", "Audio 48"),
    (4, "17_HH Meat.wav", "HH Meat"),
    (5, "18_shs_roam_breaks_loop_120_surge_full.wav", "shs_roam_breaks_loop_120_surge_full"),
    (6, "45_KSHMR_sok5_fx_impact_high_spark.wav", "KSHMR_sok5_fx_impact_high_spark"),
    (7, "35_Bass Oliver.wav", "Bass Oliver"),
    (8, "02_LD Saw Harm.wav", "LD Saw Harm"),
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    print("# | дорожка | режим | окно | сэмплов | срабатываний | хвостов | атак | пропуск | лишние | разброс мс | остаток дБ | полифония | база")
    for number, wav, track in SCENARIOS:
        probe = ROOT / "spikes/logic_read/probe.py"
        text = subprocess.run(
            [sys.executable, probe, "positions", PROJECT, "--track", track],
            check=True, capture_output=True, text=True,
        ).stdout
        grid_path = OUT / f"{number}.grid.json"
        grid_path.write_text(text, encoding="utf-8")
        audio, sr = sf.read(EXPORT / wav, always_2d=True)
        result = analyze.analyze(audio, sr, analyze.load_grid(grid_path))
        (OUT / f"{number}.analysis.json").write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        residual = "-" if result.residual_db is None else f"{result.residual_db:.1f}"
        base = "-" if result.base is None else f"{result.base.pitch}/{result.base.measured_pitch}"
        print(
            f"{number} | {track[:24]} | {result.mode} | {result.window_bars} | {len(result.samples)} "
            f"| {len(result.hits)} | {len(result.tails)} | {result.onsets} | {len(result.missing)} "
            f"| {len(result.extra)} | {result.spread_ms} | {residual} | {result.polyphony} | {base}"
        )


if __name__ == "__main__":
    main()
