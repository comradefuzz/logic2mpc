#!/bin/bash
# Перед git commit: sanity (база знаний, реестр тестов, синтаксис, импорт) и smoke-тесты.
# Smoke идёт, только если в индексе есть код, тесты или конфигурация набора. Полный прогон делается на /approve и /accept.
# Остальные команды Bash проходят без проверки.
cd "$CLAUDE_PROJECT_DIR" || exit 0

cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
# Команда начинается с git (возможно, с флагами -c и -C) и вызывает commit, либо идёт после ; && |
if ! echo "$cmd" | grep -Eq '(^|[;&|][[:space:]]*|^cd [^;&|]+(&&|;)[[:space:]]*)git([[:space:]]+-[cC][[:space:]]+[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)'; then
  exit 0
fi

python=python3
[ -x .venv/bin/python ] && python=.venv/bin/python
output=$("$python" -B scripts/gate.py commit 2>&1)
code=$?
if [ "$code" -eq 0 ]; then
  exit 0
fi
echo "$output" | tail -30 >&2
exit 2
