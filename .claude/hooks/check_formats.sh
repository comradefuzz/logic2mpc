#!/bin/bash
# Не даёт завершить работу, если база знаний о форматах или раздел «Реквесты» стори нарушены.
# Реестр тестов проверяется, только если менялись тесты, их конфигурация или сам реестр (сбор тестов ~2 с).
cd "$CLAUDE_PROJECT_DIR" || exit 0
python3 -B scripts/formats_check.py >&2 || exit 2
if [ -n "$(git status --porcelain -- tests scripts pytest.ini story_tests spikes 2>/dev/null)" ]; then
  python=python3
  [ -x .venv/bin/python ] && python=.venv/bin/python
  "$python" -B scripts/tests_registry.py check >&2 || exit 2
fi
exit 0
