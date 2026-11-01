---
id: LOGIC-R-005
status: applied
kind: close-open
targets: LOGIC-050
proposed-status: confirmed
applies: Logic 10.8.1
evidence: S-008, `probe.py notes` на копии 4 после правки Loop: 98 слышимых нот, столько же в MIDI-экспорте
found-in: S-008
created: 2026-10-31
resolved: 2026-10-31
---

LOGIC-R-003 закрыл LOGIC-050 гипотезой до пересчёта. Пересчёт сделан: с тремя проходами `RGN_loop` и алиасом на такте 22.5 код даёт 98 нот, расхождения с экспортом нет.

Предлагается перевести LOGIC-050 в `confirmed`: алиас не накладывается на Loop, отброшенных нот нет.
