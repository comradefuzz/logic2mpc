"""Отчёт по плану: что выбрано, что потеряно, что требует внимания."""
from __future__ import annotations

from .model import BAR
from .plan import Plan, is_exported
from .sections import crossings


def bars_text(values: list[float]) -> str:
    return ", ".join(f"{v:g}" for v in values)


def describe(edit: dict) -> list[str]:
    op = edit["op"]
    if op == "merge_pieces":
        lines = [f"{name} объединён в {edit['target']}, вхождения играет целевой кусок" for name in edit["sources"]]
    elif op == "split_piece":
        lines = [f"{edit['target']}: объединение снято"]
    elif op == "rename_group":
        lines = [f"группа {edit['group']} → {edit['name']}"]
    elif op == "merge_groups":
        lines = [f"группы {', '.join(edit['groups'])} объединены в {edit['groups'][0]}"]
    elif op == "set_code":
        lines = [f"код группы {edit['group']} → {edit['code']}"]
    elif op == "move_track":
        lines = [f"дорожка {edit['track']} перенесена в {edit['to'] or 'новую группу'}"]
    else:
        lines = [op]
    lines += [f"переименован {old} → {new}" for old, new in edit.get("renamed", {}).items()]
    return lines + [f"{name}: имя не по правилу, код не изменён" for name in edit.get("unrenamed", [])]


def render(plan: Plan) -> str:
    pieces = [p for g in plan.groups for t in g.tracks for p in t.pieces]
    lines = [
        f"# {plan.song}",
        "",
        f"Темп {plan.bpm:g}, решительность {plan.decisiveness}. Секций {len(plan.sections)}, кусков {len(pieces)}.",
    ]
    if plan.notes_extended or plan.notes_outside:
        lines.append(
            f"Спорные ноты перенесены как есть: расширенных {plan.notes_extended}, за границами региона {plan.notes_outside}."
        )
    if plan.muted_tracks:
        lines.append("Дорожки только с выключенными регионами, в проект не вошли: " + ", ".join(plan.muted_tracks) + ".")
    lines += ["", "## Секции", ""]
    lines += [f"- {s.name}: такт {s.start // BAR + 1}, {s.bars} тактов" for s in plan.sections]
    for group in plan.groups:
        used = sum(is_exported(p) for t in group.tracks for p in t.pieces)
        lines += ["", f"## {group.name}: {group.method}, пэдов {used}"]
        for track in group.tracks:
            length = f", цикл {track.cycle_bars} тактов" if track.cycle_bars else ""
            lines += ["", f"### {track.name}", "", f"Правило {track.rule}, уверенность {track.confidence}{length}."]
            if track.muted_bars:
                lines.append(f"Выключенные регионы: такты {bars_text(track.muted_bars)}.")
            if track.lost_bars:
                lines.append(f"Потеряны такты: {bars_text(track.lost_bars)}.")
            if track.replaced_bars:
                lines.append(f"Заменены образцом такты: {bars_text(track.replaced_bars)}.")
            if track.remark:
                lines.append(f"Внимание: {track.remark}.")
            for piece in track.pieces:
                ticks = [o.tick for o in piece.occurrences]
                if piece.merged_into:
                    lines.append(f"- {piece.name}: объединён в {piece.merged_into}, не экспортируется, вхождений {len(ticks)}")
                    continue
                lines.append(f"- {piece.name}: с такта {piece.bar:g}, вхождений {len(ticks)}, уверенность {piece.confidence}")
                edges = [word for word, flag in (("начало", piece.start_open), ("конец", piece.end_open)) if flag]
                if edges:
                    lines.append(f"  - {piece.name}: {' и '.join(edges)} не в нуле")
                crossed = crossings(ticks, piece.ticks - piece.lead, plan.sections)
                if crossed:
                    lines.append(f"  - через границу секции: такт {bars_text([t / BAR + 1 for t in crossed])}")
    if plan.edits:
        lines += ["", "## Правки пользователя", ""]
        lines += [f"- {text}" for edit in plan.edits for text in describe(edit)]
    return "\n".join(lines) + "\n"
