"""Имена сэмплов по правилу из CLAUDE.md. Автоматика даёт черновик, в плане имя правится пользователем."""
from __future__ import annotations

import re

SERVICE = {
    "drum", "drums", "fx", "loop", "loops", "one", "shot", "oneshot", "full", "kit", "lead", "synth",
    "bass", "perc", "percussion", "sample", "stem", "wet", "dry", "bpm",
}
KEY = re.compile(r"^[a-g](#|b)?(m|min|maj|minor|major)?$", re.IGNORECASE)
CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    out = []
    for char in text:
        low = char.lower()
        if low in CYRILLIC:
            value = CYRILLIC[low]
            out.append(value.capitalize() if char != low else value)
        else:
            out.append(char)
    return "".join(out)


def clean_name(name: str) -> str:
    """Убирает паки, темп, тональность и служебные слова, записывает слитно латиницей."""
    text = transliterate(re.sub(r"\[.*?\]", " ", name))
    if " - " in text:
        text = text.split(" - ", 1)[1]
    packed = "_" in text
    tokens = [t for t in re.split(r"[^0-9A-Za-z#]+", text) if t]
    if packed:
        while tokens and tokens[0].upper() == tokens[0]:
            tokens.pop(0)  # пак пишется большими буквами в начале имени
    elif len(tokens) > 1 and len(tokens[0]) <= 2 and tokens[0].isupper():
        tokens.pop(0)  # префикс вида дорожки: LD, PD
    kept = []
    for token in tokens:
        if token.isdigit() and packed or token.lower() in SERVICE and packed or packed and KEY.match(token):
            continue
        kept.append(token)
    return "".join(t[0].upper() + t[1:] for t in kept).replace("#", "")


def sample_name(song: str, group: str, name: str, number: int, row: int | None = None, note: str | None = None) -> str:
    label = name or f"{group.capitalize()}Trk{row}"
    tail = f"_{note}" if note else ""
    return f"{song}_{group}_{label}_{number:02d}{tail}"
