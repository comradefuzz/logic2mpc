---
id: MPC-R-011
status: applied
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: S-015, раунд 2, кейсы E01–E05 (`test-projects/mpc/spike9b/`, основа `spike7/D01 pads16`), открыты на Live 2 пользователем. E01 события без `version`: нот нет. E02 без `selected`, E03 без `version` ноты, E04 без `modifierValue*` и `modifierActiveState*`, E05 без `probability`, `ratchet`, `articulation`: ноты есть, играют
found-in: S-015
created: 2026-11-06
resolved: 2026-11-06
comment: Принят по прямому наблюдению пользователя на Live 2; номер MPC-118.
---

Предлагается записать как `single-sample`: из постоянных полей события-ноты обязательно только `events[].version` (на уровне события, не ноты). Без него нот в гриде нет. Без `selected`, без `note.version`, без `note.modifier*`, без `note.probability`, `note.ratchet`, `note.articulation` ноты есть и играют. Объясняет кейс Q02 раунда 1. Образец один на кейс.
