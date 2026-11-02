"""Сценарии приложения: анализ, подтверждение, сборка. Файлы только здесь и в адаптерах."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

from .adapters import logic, xpj
from .core import edit as editing
from .core import report, signal
from .core.analysis import analyze_track
from .core.model import BAR, Cut, Track
from .core.names import clean_name, sample_name, transliterate
from .core.plan import Group, Occurrence, Plan, PlanPiece, PlanTrack, from_json, plan_hash, to_json
from .core.sections import sections_from_markers
from .core.windows import DEFAULT


class ExportTargetError(ValueError):
    """Папка или имя проекта MPC не подходят."""


class BusyError(RuntimeError):
    """Сборка уже идёт, второй запуск отклонён."""


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
    plan, samples = from_json(text), version / "samples"
    file = transliterate(name)
    old = [out / f"{file}.xpj", out / f"{file}_[ProjectData]"]
    if not any(p.exists() for p in old):
        return xpj.write_project(plan, samples, out, name)
    # Перезапись: новый проект собирается рядом и заменяет старый целиком, сбой сборки старый не трогает.
    stage = Path(tempfile.mkdtemp(prefix=".logic2mpc-", dir=out))
    try:
        built = xpj.write_project(plan, samples, stage, name)
        for path in old:
            shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
        shutil.move(stage / f"{file}_[ProjectData]", old[1])
        shutil.move(built, old[0])
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return old[0]


class Session:
    """Правки открытой версии плана, AN-070. Правки живут в памяти до `save`, каждый `save` это новая версия."""

    def __init__(self, version: Path) -> None:
        self.version = version
        self.plan = from_json((version / "plan.json").read_text(encoding="utf-8"))
        self._source = self.identity(self.plan)
        self._history: list[tuple[Plan, dict[str, str]]] = []
        self.folder: Path | None = None
        self.name: str = self.plan.song
        self.lock = threading.Lock()

    def set_target(self, folder: Path | None, name: str | None) -> None:
        """Куда собирать проект MPC: папка и имя. Пустое значение оставляет прежнее."""
        if name is not None:
            clean = name.strip()
            clean = clean[: -len(".xpj")] if clean.lower().endswith(".xpj") else clean
            clean = clean.strip()
            file = transliterate(clean)
            if not file.strip() or file.startswith(".") or any(c in file for c in "/\\") or not file.isprintable():
                raise ExportTargetError("имя проекта пустое или содержит недопустимые символы")
            self.name = clean
        if folder is not None:
            folder = folder.expanduser()
            if not folder.is_absolute():
                raise ExportTargetError(f"нужен полный путь к папке: {folder}")
            if not folder.is_dir():
                raise ExportTargetError(f"нет папки {folder}")
            self.folder = folder.resolve()

    def target(self) -> dict:
        file = transliterate(self.name)
        project = self.folder / f"{file}.xpj" if self.folder else None
        data = self.folder / f"{file}_[ProjectData]" if self.folder else None
        return {
            "folder": str(self.folder) if self.folder else None,
            "name": self.name,
            "file": file,
            "project": str(project) if project else None,
            "data": str(data) if data else None,
            "exists": bool(project and (project.exists() or data.exists())),
        }

    @staticmethod
    def identity(plan: Plan) -> dict[str, str]:
        return {p.file: p.file for g in plan.groups for t in g.tracks for p in t.pieces}

    @property
    def dirty(self) -> bool:
        return bool(self._history)

    @property
    def confirmed(self) -> bool:
        path = self.version / "confirmed.json"
        if self.dirty or not path.is_file():
            return False
        text = (self.version / "plan.json").read_text(encoding="utf-8")
        return json.loads(path.read_text(encoding="utf-8"))["plan_sha256"] == plan_hash(text)

    def edit(self, op: dict) -> None:
        self.refuse_while_busy()
        new = editing.apply(self.plan, op)
        inverse = {new_name: old for old, new_name in new.edits[-1].get("renamed", {}).items()}
        source = {}
        for g in new.groups:
            for t in g.tracks:
                for p in t.pieces:
                    old_file = f"{inverse[p.name]}.wav" if p.name in inverse else p.file
                    source[p.file] = self._source[old_file]
        self._history.append((self.plan, self._source))
        self.plan, self._source = new, source

    def refuse_while_busy(self) -> None:
        if self.busy:
            raise BusyError("идёт сборка, правки недоступны")

    def undo(self) -> None:
        self.refuse_while_busy()
        if not self._history:
            raise editing.EditError("нечего отменять")
        self.plan, self._source = self._history.pop()

    def audio(self, name: str) -> Path:
        for g in self.plan.groups:
            for t in g.tracks:
                for p in t.pieces:
                    if p.name == name:
                        return self.version / "samples" / self._source[p.file]
        raise KeyError(name)

    def save(self) -> Path:
        """Пишет правки новой версией. Прежняя не меняется, подтверждение не переносится."""
        folder = next_version(self.version.parent)
        try:
            (folder / "samples").mkdir()
            for g in self.plan.groups:
                for t in g.tracks:
                    for p in t.pieces:
                        shutil.copy2(self.version / "samples" / self._source[p.file], folder / "samples" / p.file)
            (folder / "plan.json").write_text(to_json(self.plan), encoding="utf-8")
            (folder / "report.md").write_text(report.render(self.plan), encoding="utf-8")
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        self.version = folder
        self._source = self.identity(self.plan)
        self._history = []
        return folder

    def require_saved(self) -> None:
        if self.dirty:
            raise ConfirmationError("правки не сохранены: сначала сохранить версию")

    def confirm(self) -> Path:
        self.require_saved()
        return confirm(self.version)

    @property
    def busy(self) -> bool:
        return self.lock.locked()

    def build(self, out: Path, name: str) -> Path:
        self.require_saved()
        if not self.lock.acquire(blocking=False):
            raise BusyError("сборка уже идёт")
        try:
            return build(self.version, out, name)
        finally:
            self.lock.release()

    def finish(self, overwrite: bool = False) -> Path:
        """Одно действие пользователя: сохранить правки версией, подтвердить её и собрать проект.

        Готовый проект с тем же именем перезаписывается только с явным `overwrite`: файл `.xpj` и папка
        `_[ProjectData]` заменяются целиком, старых сэмплов не остаётся.
        """
        if self.folder is None:
            raise ExportTargetError("выберите папку для проекта")
        if self.target()["exists"] and not overwrite:
            raise ExportTargetError("проект с таким именем уже есть: нужно подтверждение перезаписи")
        if not self.lock.acquire(blocking=False):
            raise BusyError("сборка уже идёт")
        try:
            if self.dirty:
                self.save()
            if not self.confirmed:
                self.confirm()
            return build(self.version, self.folder, self.name)
        finally:
            self.lock.release()
