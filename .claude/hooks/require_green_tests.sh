#!/bin/bash
# Не даёт завершить работу при красных тестах, если менялся Python-код.
# Полный прогон идёт только когда стори дошла до review или acceptance,
# на остальных этапах хук молчит (весь набор идёт около трёх минут).
cd "$CLAUDE_PROJECT_DIR" || exit 0

if ! grep -lE '^status: (review|acceptance)$' stories/S-*.md >/dev/null 2>&1; then
  exit 0
fi
if [ -z "$(git status --porcelain -- '*.py' 2>/dev/null)" ]; then
  exit 0
fi

python=python3
[ -x .venv/bin/python ] && python=.venv/bin/python
"$python" -c 'import pytest' 2>/dev/null || exit 0

output=$("$python" -m pytest -q 2>&1)
code=$?
# Код 5 означает, что тестов пока нет.
if [ "$code" -eq 0 ] || [ "$code" -eq 5 ]; then
  exit 0
fi

echo "$output" | tail -30 >&2
exit 2
