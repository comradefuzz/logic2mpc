"""Сценарии приложения: анализ, подтверждение, сборка. Файлы только здесь и в адаптерах."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

from .adapters import logic, xpj
from .core import report, signal
from .core.analysis import analyze_track
from .core.model import BAR, Cut, Track
from .core.names import clean_name, sample_name
from .core.plan import Group, Occurrence, Plan, PlanPiece, PlanTrack, from_json, plan_hash, to_json
from .core.sections import sections_from_markers
from .core.windows import DEFAULT


class ConfirmationError(RuntimeError):
    """Проект собирается только по подтверждённому плану."""


def export_files(folder: Path) -> dict[int, Path]:
    return {int(m.group(1)): p for p in folder.glob("*.wav") if (m := re.match(r"(\d+)_", p.name))}


def audible(track: Track) -> bool:
    return any(r.notes and not r.muted for r in track.midi_regions) or any(not r.muted for r in track.audio_regions)


def next_version(out: Path) -> Path:
    numbers = [int(p.name[1:]) for p in out.glob("v*") if p.is_dir() and p.name[1:].isdigit()]
    folder = out / f"v{max(numbers, default=0) + 1}"
    folder.mkdir(parents=True)
    return folder


def plan_track(
    track: Track, cut: Cut, audio: np.ndarray, sr: int, bpm: float, song: str, code: str, used: Counter, samples: Path
) -> PlanTrack:
    label = clean_name(track.name)
    pieces = []
    for piece in cut.pieces:
        used[(code, label or track.row)] += 1
        name = sample_name(song, code, label, used[(code, label or track.row)], row=track.row + 1)
        file = f"{name}.wav"
        sf.write(samples / file, audio[piece.start : piece.end], sr, subtype="PCM_24")
        ticks = signal.frames_to_ticks(piece.end - piece.start, bpm, sr)
        occurrences = [Occurrence(o.tick, o.gain, o.length) for o in sorted(piece.occurrences, key=lambda o: o.tick)]
        bar = round(signal.frames_to_ticks(piece.start + piece.lead, bpm, sr) / BAR + 1, 3)
        pieces.append(PlanPiece(
            name, file, bar, ticks, piece.confidence, occurrences,
            start_open=piece.start_open, end_open=piece.end_open,
            lead=signal.frames_to_ticks(piece.lead, bpm, sr),
        ))
    return PlanTrack(
        track.row + 1, track.name, cut.rule, cut.confidence, pieces,
        cycle_bars=cut.cycle_bars, lost_bars=cut.lost_bars, muted_bars=cut.muted_bars,
        replaced_bars=cut.replaced_bars, remark=cut.remark,
    )


def analyze(project: Path, export: Path, groups_file: Path, out: Path, decisiveness: float = DEFAULT) -> Path:
    """Режет дорожки, пишет новую версию: сэмплы, план, отчёт. Проект MPC здесь не создаётся."""
    config = json.loads(groups_file.read_text(encoding="utf-8"))
    song = logic.read_project(project)
    files = export_files(export)
    content = [t for t in song.tracks if audible(t)]
    muted = [f"{t.name} (строка {t.row + 1})" for t in song.tracks if not audible(t) and (t.midi_regions or t.audio_regions)]
    outside = [t.name for t in content if t.group is None]
    if outside:
        raise ValueError("дорожки вне стека, группы у них нет: " + ", ".join(outside))
    unknown = sorted({t.group for t in content} - set(config["groups"]))
    if unknown:
        raise ValueError("нет группы в настройках: " + ", ".join(unknown))
    lost = [t.name for t in content if t.row + 1 not in files]
    if lost:
        raise FileNotFoundError("нет файла экспорта у дорожек с регионами: " + ", ".join(lost))
    folder = next_version(out)
    samples = folder / "samples"
    samples.mkdir()
    used: Counter = Counter()
    groups = []
    for name, settings in config["groups"].items():
        tracks = []
        for track in (t for t in content if t.group == name):
            print(f"{name}: {track.name}", flush=True)
            audio, sr = sf.read(files[track.row + 1], always_2d=True)
            cut = analyze_track(track, audio, sr, song.bpm, decisiveness)
            tracks.append(plan_track(track, cut, audio, sr, song.bpm, config["song"], settings["code"], used, samples))
        groups.append(Group(name, settings["code"], settings.get("method", "drum"), tracks))
    ends = [o.tick + p.ticks for g in groups for t in g.tracks for p in t.pieces for o in p.occurrences]
    plan = Plan(
        config["song"], song.bpm, song.sr, decisiveness, sections_from_markers(song.markers, max(ends, default=BAR)),
        groups, notes_extended=song.notes_extended, notes_outside=song.notes_outside, muted_tracks=muted,
    )
    (folder / "plan.json").write_text(to_json(plan), encoding="utf-8")
    (folder / "report.md").write_text(report.render(plan), encoding="utf-8")
    return folder


def confirm(version: Path) -> Path:
    """Запись подтверждения пользователя: подтверждён именно этот текст плана."""
    digest = plan_hash((version / "plan.json").read_text(encoding="utf-8"))
    path = version / "confirmed.json"
    path.write_text(json.dumps({"plan_sha256": digest}, indent=1) + "\n", encoding="utf-8")
    return path


def build(version: Path, out: Path, name: str) -> Path:
    text = (version / "plan.json").read_text(encoding="utf-8")
    path = version / "confirmed.json"
    if not path.is_file():
        raise ConfirmationError("план не подтверждён: сначала confirm")
    if json.loads(path.read_text(encoding="utf-8"))["plan_sha256"] != plan_hash(text):
        raise ConfirmationError("план изменён после подтверждения: нужен новый confirm")
    return xpj.write_project(from_json(text), version / "samples", out, name)
