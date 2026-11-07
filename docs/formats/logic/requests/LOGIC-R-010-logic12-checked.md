---
id: LOGIC-R-010
status: applied
kind: close-open
targets: LOGIC-101
proposed-status: single-sample
applies: Logic 12.3.1 (6682)
evidence: S-027, `test-projects/reference/L12/Spike Control copy.logicx`, `ProjectData` альтернативы 000 версии 0x09D1; story_tests/S-027/test_logic12.py
found-in: S-027
created: 2026-11-07
resolved: 2026-11-08
comment: Принято по решению пользователя без отдельной проверки (LOGIC-101)
---

Logic 12 проверена на одном контрольном проекте (7 дорожек, смены темпа и размера, маркеры, MIDI и аудиорегионы). Контейнер тот же, все 612 записей проходятся до конца, новых тегов нет. Темп, размер, маркеры, строки дорожек, аудиорегионы и ноты читаются кодом 10.8.1 с обходом проверки версии и совпадают с оригиналом поэлементно.

Предлагается записать в LOGIC-101: Logic 12.3.1 проверена на Spike Control как `single-sample`. Не проверялось: большие проекты (Elated, Pyro), Drummer и Session Players в действии, Track Alternatives, Logic 11. Logic 11 остаётся `open`.
