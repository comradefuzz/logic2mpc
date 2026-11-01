"""Export Plan: документ в файле, не зависит от интерфейса."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from .sections import Section

PLAN_VERSION = 1


@dataclass
class Occurrence:
    tick: int
    gain: float = 1.0
    length: int | None = None


@dataclass
class PlanPiece:
    name: str
    file: str
    bar: float
    ticks: int
    confidence: float
    occurrences: list[Occurrence]
    export: bool = True
    origin: str = "rule"
    note: str | None = None
    start_open: bool = False
    end_open: bool = False
    lead: int = 0


@dataclass
class PlanTrack:
    row: int
    name: str
    rule: str
    confidence: float
    pieces: list[PlanPiece]
    origin: str = "rule"
    cycle_bars: int | None = None
    lost_bars: list[float] = field(default_factory=list)
    muted_bars: list[float] = field(default_factory=list)
    replaced_bars: list[float] = field(default_factory=list)
    remark: str | None = None


@dataclass
class Group:
    name: str
    code: str
    method: str
    tracks: list[PlanTrack]
    origin: str = "user"


@dataclass
class Plan:
    song: str
    bpm: float
    sr: int
    decisiveness: float
    sections: list[Section]
    groups: list[Group]
    version: int = PLAN_VERSION
    notes_extended: int = 0
    notes_outside: int = 0
    muted_tracks: list[str] = field(default_factory=list)


def to_json(plan: Plan) -> str:
    return json.dumps(asdict(plan), ensure_ascii=False, indent=1) + "\n"


def from_json(text: str) -> Plan:
    data = json.loads(text)
    data["sections"] = [Section(**s) for s in data["sections"]]
    groups = []
    for group in data["groups"]:
        tracks = []
        for track in group["tracks"]:
            pieces = []
            for piece in track["pieces"]:
                piece["occurrences"] = [Occurrence(**o) for o in piece["occurrences"]]
                pieces.append(PlanPiece(**piece))
            track["pieces"] = pieces
            tracks.append(PlanTrack(**track))
        group["tracks"] = tracks
        groups.append(Group(**group))
    data["groups"] = groups
    return Plan(**data)


def plan_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
