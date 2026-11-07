#!/bin/bash
# Не даёт завершить работу, если база знаний о форматах, раздел «Реквесты» стори или реестр тестов нарушены.
cd "$CLAUDE_PROJECT_DIR" || exit 0
python3 -B scripts/formats_check.py >&2 || exit 2
python=python3
[ -x .venv/bin/python ] && python=.venv/bin/python
"$python" -B scripts/tests_registry.py check >&2 || exit 2
exit 0
