"""Отчёт по плану: что выбрано, что потеряно, что требует внимания."""
from __future__ import annotations

from .model import BAR
from .plan import Plan
from .sections import crossings


def bars_text(values: list[float]) -> str:
    return ", ".join(f"{v:g}" for v in values)


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
        used = sum(p.export for t in group.tracks for p in t.pieces)
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
                lines.append(f"- {piece.name}: с такта {piece.bar:g}, вхождений {len(ticks)}, уверенность {piece.confidence}")
                edges = [word for word, flag in (("начало", piece.start_open), ("конец", piece.end_open)) if flag]
                if edges:
                    lines.append(f"  - {piece.name}: {' и '.join(edges)} не в нуле")
                crossed = crossings(ticks, piece.ticks - piece.lead, plan.sections)
                if crossed:
                    lines.append(f"  - через границу секции: такт {bars_text([t / BAR + 1 for t in crossed])}")
    return "\n".join(lines) + "\n"
