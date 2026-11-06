#!/bin/bash
# Перед git commit прогоняет весь pytest и блокирует коммит при красных тестах.
# Остальные команды Bash проходят без проверки.
cd "$CLAUDE_PROJECT_DIR" || exit 0

cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

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
echo "Коммит заблокирован: тесты красные." >&2
exit 2
