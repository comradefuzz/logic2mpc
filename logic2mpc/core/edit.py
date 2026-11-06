"""Правки плана пользователем, AN-070. Чистые функции: новый план на выходе, старый не меняется."""
from __future__ import annotations

import copy
import re

from .plan import Group, Plan, PlanPiece, PlanTrack, is_exported

PADS = 128
NEW_GROUP = "Новая группа"


class EditError(ValueError):
    """Правка отклонена, план не изменён."""


def apply(plan: Plan, op: dict) -> Plan:
    handler = HANDLERS.get(op.get("op"))
    if handler is None:
        raise EditError(f"неизвестная правка: {op.get('op')}")
    new = copy.deepcopy(plan)
    try:
        entry = handler(new, op)
    except EditError:
        raise
    except KeyError as error:
        raise EditError(f"в правке нет поля {error}") from None
    except (TypeError, AttributeError, ValueError):
        raise EditError("поля правки неверного типа") from None
    new.edits.append({**op, **entry})
    return new


def find_track(plan: Plan, row: int) -> tuple[Group, PlanTrack]:
    for group in plan.groups:
        for track in group.tracks:
            if track.row == row:
                return group, track
    raise EditError(f"нет дорожки {row}")


def find_group(plan: Plan, name: str) -> Group:
    for group in plan.groups:
        if group.name == name:
            return group
    raise EditError(f"нет группы {name}")


def find_piece(track: PlanTrack, name: str) -> PlanPiece:
    for piece in track.pieces:
        if piece.name == name:
            return piece
    raise EditError(f"в дорожке {track.name} нет фрагмента {name}")


def merge_pieces(plan: Plan, op: dict) -> dict:
    _, track = find_track(plan, op["track"])
    sources = list(op["sources"])
    if not sources:
        raise EditError("не выбраны фрагменты для объединения")
    target = find_piece(track, op["target"])
    if op["target"] in sources:
        raise EditError("целевой фрагмент не может быть среди объединяемых")
    if target.merged_into:
        raise EditError(f"{target.name} уже объединён в {target.merged_into}")
    for name in sources:
        piece = find_piece(track, name)
        if piece.merged_into:
            raise EditError(f"{name} уже объединён в {piece.merged_into}")
    for piece in track.pieces:
        if piece.name in sources or piece.merged_into in sources:
            piece.merged_into = target.name
            piece.origin = "user"
    target.origin = "user"
    track.origin = "user"
    return {}


def split_piece(plan: Plan, op: dict) -> dict:
    group, track = find_track(plan, op["track"])
    target = find_piece(track, op["target"])
    absorbed = [p for p in track.pieces if p.merged_into == target.name]
    if not absorbed:
        raise EditError(f"{target.name} не объединяет фрагментов")
    for piece in absorbed:
        piece.merged_into = None
        piece.origin = "user"
    check_pads(group)
    return {}


def rename_group(plan: Plan, op: dict) -> dict:
    group = find_group(plan, op["group"])
    name = op["name"].strip()
    if not name:
        raise EditError("имя группы пустое")
    if name != group.name and any(g.name == name for g in plan.groups):
        raise EditError(f"группа {name} уже есть")
    group.name = name
    group.origin = "user"
    return {}


def count_pads(group: Group) -> int:
    return sum(is_exported(p) for t in group.tracks for p in t.pieces)


def check_pads(group: Group) -> None:
    if count_pads(group) > PADS:
        raise EditError(f"в группе {group.name} {count_pads(group)} фрагментов при лимите {PADS} пэдов")


def split_name(song: str, code: str, name: str) -> tuple[str, int, str] | None:
    """`КОД_ГРУППА_Имя_NN[_нота]`: имя без номера, номер, хвост."""
    match = re.fullmatch(rf"{re.escape(song)}_{re.escape(code)}_(.+?)_(\d+)(_[A-G][#b]?-?\d)?", name)
    if not match:
        return None
    return match.group(1), int(match.group(2)), match.group(3) or ""


def rename_for(
    plan: Plan, track: PlanTrack, old_code: str, new_code: str, taken: set[str], skipped: list[str]
) -> dict[str, str]:
    """Новые имена сэмплов дорожки под код группы. Номера внутри `(код, имя)` уникальны."""
    if old_code == new_code:
        return {}
    renamed: dict[str, str] = {}
    for piece in track.pieces:
        parts = split_name(plan.song, old_code, piece.name)
        if parts is None:
            skipped.append(piece.name)
            continue
        label, _, tail = parts
        number = 1
        while f"{plan.song}_{new_code}_{label}_{number:02d}{tail}" in taken:
            number += 1
        new = f"{plan.song}_{new_code}_{label}_{number:02d}{tail}"
        taken.add(new)
        renamed[piece.name] = new
    for piece in track.pieces:
        if piece.merged_into in renamed:
            piece.merged_into = renamed[piece.merged_into]
    for piece in track.pieces:
        if piece.name in renamed:
            piece.name = renamed[piece.name]
            piece.file = f"{piece.name}.wav"
    return renamed


def all_names(plan: Plan) -> set[str]:
    return {p.name for g in plan.groups for t in g.tracks for p in t.pieces}


def move_into(plan: Plan, track: PlanTrack, source: Group, target: Group, skipped: list[str]) -> dict[str, str]:
    renamed = rename_for(plan, track, source.code, target.code, all_names(plan), skipped)
    track.origin = "user"
    target.tracks.append(track)
    return renamed


def merge_groups(plan: Plan, op: dict) -> dict:
    names = list(dict.fromkeys(op["groups"]))
    if len(names) < 2:
        raise EditError("для объединения нужно две группы и больше")
    groups = [find_group(plan, n) for n in names]
    base = groups[0]
    renamed: dict[str, str] = {}
    skipped: list[str] = []
    for group in groups[1:]:
        for track in group.tracks:
            renamed.update(move_into(plan, track, group, base, skipped))
        plan.groups.remove(group)
    base.origin = "user"
    check_pads(base)
    return {"renamed": renamed, "unrenamed": skipped}


def set_code(plan: Plan, op: dict) -> dict:
    group = find_group(plan, op["group"])
    code = op["code"]
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z]{2}", code):
        raise EditError("код группы это две заглавные латинские буквы")
    taken = all_names(plan)
    renamed: dict[str, str] = {}
    skipped: list[str] = []
    for track in group.tracks:
        renamed.update(rename_for(plan, track, group.code, code, taken, skipped))
    group.code = code
    group.origin = "user"
    return {"renamed": renamed, "unrenamed": skipped}


def move_track(plan: Plan, op: dict) -> dict:
    source, track = find_track(plan, op["track"])
    to = op["to"]
    if to is None:
        n = 1
        while (name := NEW_GROUP if n == 1 else f"{NEW_GROUP} {n}") in {g.name for g in plan.groups}:
            n += 1
        target = Group(name, source.code, source.method, [], origin="user")
        plan.groups.append(target)
    else:
        target = find_group(plan, to)
        if target is source:
            raise EditError("дорожка уже в этой группе")
    source.tracks.remove(track)
    skipped: list[str] = []
    renamed = move_into(plan, track, source, target, skipped)
    if not source.tracks:
        plan.groups.remove(source)
    check_pads(target)
    return {"renamed": renamed, "unrenamed": skipped}


HANDLERS = {
    "merge_pieces": merge_pieces,
    "split_piece": split_piece,
    "rename_group": rename_group,
    "merge_groups": merge_groups,
    "move_track": move_track,
    "set_code": set_code,
}
