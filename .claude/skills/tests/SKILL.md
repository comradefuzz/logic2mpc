---
name: tests
description: Явно прогнать полный набор pytest
argument-hint: [путь или -k выражение]
disable-model-invocation: true
---

Прогон тестов: $ARGUMENTS

Запусти `.venv/bin/python -m pytest -q $ARGUMENTS` из корня проекта (без аргументов это полный общий набор `tests` и `scripts`; быстрый smoke: `-m smoke`, уровни контроля: `scripts/gate.py sanity|commit|full`; тесты стори: `story_tests/S-NNN`; актуализация: `/tests-audit`) (полный набор идёт около трёх минут, запускай в фоне). Сообщи итог: сколько прошло, упало, пропущено. При падениях покажи имена тестов и суть ошибок, ничего не чини без просьбы.
