#!/usr/bin/env python3
"""Собирает BOARD.md из заголовков файлов stories/S-*.md."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAITING = {
    "analysis": "ответить на вопросы",
    "plan-review": "одобрить план: `/approve {num}`",
    "acceptance": "принять: `/accept {num}`",
    "blocked": "снять блокировку",
}
ACTIVE = ("tests", "dev", "review")
KNOWN = (*WAITING, *ACTIVE, "done")


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    type: str
    status: str
    path: str

    @property
    def num(self) -> str:
        return self.id.removeprefix("S-")


def parse_story(text: str, path: str) -> Story:
    match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    fields: dict[str, str] = {}
    if match:
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
    return Story(
        id=fields.get("id", "?"),
        title=fields.get("title", "?"),
        type=fields.get("type", "?"),
        status=fields.get("status", "?"),
        path=path,
    )


def link(story: Story) -> str:
    return f"[{story.id}]({story.path})"


def render(stories: list[Story]) -> str:
    waiting = [s for s in stories if s.status in WAITING]
    active = [s for s in stories if s.status in ACTIVE]
    done = [s for s in stories if s.status == "done"]
    invalid = [s for s in stories if s.status not in KNOWN]

    lines = ["# Доска стори", "", "Файл генерируется, вручную не править.", ""]

    lines += ["## Ждёт тебя", ""]
    if waiting:
        lines += ["| Стори | Название | Статус | Что сделать |", "|---|---|---|---|"]
        for s in waiting:
            action = WAITING[s.status].format(num=s.num)
            lines.append(f"| {link(s)} | {s.title} | `{s.status}` | {action} |")
    else:
        lines.append("Ничего.")

    lines += ["", "## В работе у Claude", ""]
    if active:
        lines += ["| Стори | Название | Статус |", "|---|---|---|"]
        lines += [f"| {link(s)} | {s.title} | `{s.status}` |" for s in active]
    else:
        lines.append("Ничего.")

    if invalid:
        lines += ["", "## Неизвестный статус", ""]
        lines += [f"- {link(s)} {s.title}: `{s.status}`" for s in invalid]

    lines += ["", "## Готово", ""]
    lines += [f"- {link(s)} {s.title}" for s in done] or ["Пока ничего."]
    return "\n".join(lines) + "\n"


def main() -> None:
    paths = sorted((ROOT / "stories").glob("S-*.md"))
    stories = [
        parse_story(p.read_text(encoding="utf-8"), p.relative_to(ROOT).as_posix())
        for p in paths
    ]
    (ROOT / "BOARD.md").write_text(render(stories), encoding="utf-8")


if __name__ == "__main__":
    main()
