---
name: tests
description: Явно прогнать полный набор pytest
argument-hint: [путь или -k выражение]
disable-model-invocation: true
---

Прогон тестов: $ARGUMENTS

Запусти `.venv/bin/python -m pytest -q $ARGUMENTS` из корня проекта (без аргументов это общий набор `tests` и `scripts`; тесты стори: `story_tests/S-NNN`; актуализация: `/tests-audit`) (полный набор идёт около трёх минут, запускай в фоне). Сообщи итог: сколько прошло, упало, пропущено. При падениях покажи имена тестов и суть ошибок, ничего не чини без просьбы.
