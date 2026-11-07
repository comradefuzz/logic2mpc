"""Сборка проекта MPC по описанию формата (`xpj_spec`), без донорского проекта.

Устройство файла: docs/formats/mpc/, контракт экспортёра: docs/contracts/xpj-export.md. Вход проверяется по JSON Schema
`logic2mpc/spec/export-plan.schema.json` до записи.
"""
from __future__ import annotations

import gzip  # noqa: F401  (доступен тестам как xpj.gzip)
import json
import shutil
import struct
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

import jsonschema

from ..core.model import BAR
from ..core.names import transliterate
from ..core.plan import Group, Occurrence, Plan, PlanPiece, is_exported, occurrences_of
from ..core.sections import Section, place
from . import xpj_spec
from .mpcfile import Number, Project, dump, load, pack, parse, render  # noqa: F401  (часть интерфейса модуля)

PADS = 128
DEFAULT_NOTE_ON_FROM = Fraction(2, 4)
MUTE_GROUPS = 32
HANDS = "HANDS"
MIN_VELOCITY = 0.05
SCHEMA = xpj_spec.SPEC / "export-plan.schema.json"
SERVICE_LOSS = (
    "Проект собран без служебных треков Out, Submix, Return (MPC-112): в MIX нет Submix и Return, "
    "Live 2 их не пересоздаёт"
)


class ContractError(ValueError):
    """План не соответствует контракту экспортёра."""


@dataclass
class ExportResult:
    path: Path
    losses: list[str] = field(default_factory=list)


def validate_plan(plan: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(plan), key=lambda e: list(e.absolute_path))
    if errors:
        where = "/".join(str(x) for x in errors[0].absolute_path) or "план"
        raise ContractError(f"план не соответствует контракту: {where}: {errors[0].message}")


def frames(path: Path) -> int:
    """Число кадров по заголовку RIFF."""
    raw = path.read_bytes()
    offset = 12
    block = 0
    while offset + 8 <= len(raw):
        size = struct.unpack_from("<I", raw, offset + 4)[0]
        if raw[offset : offset + 4] == b"fmt ":
            block = struct.unpack_from("<H", raw, offset + 20)[0]
        elif raw[offset : offset + 4] == b"data":
            return size // block
        offset += 8 + size + size % 2
    raise ValueError(f"нет данных в {path}")


def exported(group: Group) -> list[PlanPiece]:
    return [p for t in group.tracks for p in t.pieces if is_exported(p)]


def plays(group: Group, piece: PlanPiece) -> list[Occurrence]:
    """Вхождения фрагмента вместе с вхождениями слитых в него, AN-070."""
    track = next(t for t in group.tracks if any(p is piece for p in t.pieces))
    return occurrences_of(track, piece)


def clip_of(value: dict[str, Any], track: str) -> dict[str, Any]:
    return next(c["value"] for c in value["trackClipMaps"][0] if c["key"] == track)


def notes_of(value: dict[str, Any], track: str) -> list[tuple[int, int]]:
    return [(e["time"], e["note"]["note"]) for e in clip_of(value, track)["eventList"]["events"]]


def add_notes(
    by_key: dict[int, dict[str, Any]], track: str, pitch: int, piece: PlanPiece, occurrences: list[Occurrence],
    sections: list[Section],
) -> int:
    """Ставит ноты фрагмента в клипы секций. Возвращает число нот, у которых длина усечена по концу секции."""
    cut = 0
    loudest = max((o.gain for o in occurrences), default=0.0)
    for occurrence in occurrences:
        number, attack = place(occurrence.tick, sections)
        tick = max(attack - piece.lead, 0)
        room = sections[number].bars * BAR - tick
        velocity = max(occurrence.gain / loudest, MIN_VELOCITY) if loudest else 1.0
        wanted = occurrence.length or piece.ticks
        length = max(min(wanted, room), 1)
        cut += length < wanted
        event = xpj_spec.note_event(tick, pitch, velocity, length)
        clip_of(by_key[number], track)["eventList"]["events"].append(event)
    return cut


def threshold_ticks(value: Fraction | str) -> int:
    """Порог режима Note On в тиках из доли такта (`2/4`, `Fraction`). Не больше 0 или не доля: `ValueError`."""
    try:
        share = Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"порог note_on_from не доля такта: {value!r}") from None
    if share <= 0:
        raise ValueError(f"порог note_on_from должен быть больше 0: {value!r}")
    return int(share * BAR)


def past_section_end(piece: PlanPiece, occurrences: list[Occurrence], sections: list[Section]) -> int:
    """Число вхождений, которые звучат за концом своей секции."""
    count = 0
    for occurrence in occurrences:
        number, attack = place(occurrence.tick, sections)
        room = sections[number].bars * BAR - max(attack - piece.lead, 0)
        count += (occurrence.length or piece.ticks) > room
    return count


def trigger_mode(piece: PlanPiece, occurrences: list[Occurrence], sections: list[Section], limit: int) -> int:
    """AN-068: 2 (Note On) у длинного образца, целиком звучащего в своих секциях, иначе 0 (One Shot)."""
    return 2 if piece.ticks > limit and not past_section_end(piece, occurrences, sections) else 0


def mute_groups(group: Group) -> tuple[list[int], int]:
    """AN-069: mute group для экспортируемых фрагментов группы плана, по порядку `exported(group)`.

    Фрагменты одной дорожки Logic, оставшиеся отдельными (два и больше), получают общий номер от 1 по порядку
    дорожек. Одиночные фрагменты и дорожки сверх `MUTE_GROUPS` остаются в 0. Второе значение это число дорожек,
    которым группы не хватило.
    """
    numbers: list[int] = []
    next_group = 1
    short = 0
    for track in group.tracks:
        kept = [p for p in track.pieces if is_exported(p)]
        if len(kept) < 2:
            numbers += [0] * len(kept)
        elif next_group > MUTE_GROUPS:
            numbers += [0] * len(kept)
            short += 1
        else:
            numbers += [next_group] * len(kept)
            next_group += 1
    return numbers, short


def check(plan: Plan, samples: Path) -> None:
    """Всё проверяется до записи: без сэмпла Live 2 покажет Sample not found, см. MPC-083."""
    for group in plan.groups:
        pieces = exported(group)
        if len(pieces) > PADS:
            raise ValueError(f"группа {group.name}: {len(pieces)} фрагментов при лимите {PADS} пэдов")
    titles = [HANDS] + [transliterate(g.name) for g in plan.groups]
    twins = sorted({t for t in titles if titles.count(t) > 1})
    if twins:
        raise ValueError("совпадают имена треков после транслитерации: " + ", ".join(twins))
    missing = sorted(p.file for g in plan.groups for p in exported(g) if not (samples / p.file).is_file())
    if missing:
        raise FileNotFoundError("нет сэмплов: " + ", ".join(missing))


def drum_track(
    number: int, title: str, pieces: list[PlanPiece], modes: list[int], mutes: list[int], samples: Path, bpm: float,
) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    """Трек HANDS (без фрагментов) или трек группы: 128 пэдов, на первых сэмплы фрагментов."""
    track = xpj_spec.drum_track(title, armed=number == 0)
    program = track["program"]
    copies = []
    for index in range(PADS):
        if index < len(pieces):
            piece = pieces[index]
            path = f"{piece.name}.wav"
            program["samples"].append(xpj_spec.sample_entry(piece.name, path, bpm, in_program=True))
            copies.append((samples / piece.file, path))
            made = xpj_spec.pad(number * PADS + index, (piece.name, path, frames(samples / piece.file)), bpm, modes[index], mutes[index])
        else:
            made = xpj_spec.pad(number * PADS + index, None, bpm)
        program["drum"]["instruments"].append(made)
    return track, copies


def export_project(
    plan: Plan, samples: Path, out: Path, name: str, note_on_from: Fraction | str = DEFAULT_NOTE_ON_FROM,
) -> ExportResult:
    validate_plan(asdict(plan))
    limit = threshold_ticks(note_on_from)
    check(plan, samples)
    name = transliterate(name)
    bpm = float(plan.bpm)
    data = xpj_spec.root(bpm)
    losses = [SERVICE_LOSS]
    copies: list[tuple[Path, str]] = []
    chosen: list[tuple[str, Group, list[PlanPiece]]] = []
    titles = [HANDS]
    for number, group in enumerate([None, *plan.groups]):
        pieces = exported(group) if group else []
        title = transliterate(group.name) if group else HANDS
        modes = [trigger_mode(p, plays(group, p), plan.sections, limit) for p in pieces] if group else []
        mutes, short = mute_groups(group) if group else ([], 0)
        if short:
            losses.append(f"Не хватило mute group (максимум {MUTE_GROUPS}) в группе «{title}»: дорожек без группы {short}")
        track, made = drum_track(number, title, pieces, modes, mutes, samples, bpm)
        data["tracks"].append(track)
        copies += made
        for piece in pieces:
            data["samples"].append(xpj_spec.sample_entry(piece.name, f"{piece.name}.wav", bpm))
        if group:
            chosen.append((title, group, pieces))
            titles.append(title)
    made_sequences = []
    for number, section in enumerate(plan.sections):
        pulses = section.bars * BAR
        item = xpj_spec.sequence(number, transliterate(section.name), section.bars, pulses, bpm)
        item["value"]["trackClipMaps"] = [sorted((xpj_spec.clip(t, pulses) for t in titles), key=lambda c: c["key"])]
        made_sequences.append(item)
    data["sequences"] = list(reversed(made_sequences))
    by_key = {s["key"]: s["value"] for s in data["sequences"]}
    cut = 0
    for title, group, pieces in chosen:
        notes = next(t for t in data["tracks"] if t["name"] == title)["program"]["padNoteMap"]["noteForPad"]
        for pad, piece in enumerate(pieces):
            cut += add_notes(by_key, title, notes[f"value{pad}"], piece, plays(group, piece), plan.sections)
    for sequence in data["sequences"]:
        for clips in sequence["value"]["trackClipMaps"]:
            for item in clips:
                item["value"]["eventList"]["events"].sort(key=lambda e: e["time"])
    if cut:
        late = [p for _, g, pieces in chosen for p in pieces if past_section_end(p, plays(g, p), plan.sections)]
        losses.append(f"Звучит за концом секции (One Shot): образцов {len(late)}, вхождений {cut}")
    merged = sum(1 for g in plan.groups for t in g.tracks for p in t.pieces if p.merged_into is not None)
    if merged:
        losses.append(f"Фрагментов слито в другие, пэда у них нет, ноты перенесены на основной: {merged}")
    out.mkdir(parents=True, exist_ok=True)
    folder = out / f"{name}_[ProjectData]"
    folder.mkdir(exist_ok=True)
    for source, target in copies:
        shutil.copy2(source, folder / target)
    path = out / f"{name}.xpj"
    path.write_bytes(pack(render(Project(xpj_spec.header(), data))))
    return ExportResult(path, losses)


def write_project(plan: Plan, samples: Path, out: Path, name: str) -> Path:
    return export_project(plan, samples, out, name).path
