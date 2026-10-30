#!/bin/bash
# Не даёт завершить работу, если база знаний о форматах или раздел «Реквесты» стори нарушены.
cd "$CLAUDE_PROJECT_DIR" || exit 0
python3 -B scripts/formats_check.py >&2 || exit 2
exit 0
