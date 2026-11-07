---
id: LOGIC-R-012
status: applied
kind: add
targets:
proposed-status: single-sample
applies: Logic 12.3.1 (6682)
evidence: S-027, Spike Control: записи, добавленные в 000 против оригинала; Trak 94 байта против 93
found-in: S-027
created: 2026-11-07
resolved: 2026-11-08
comment: Принято по решению пользователя без отдельной проверки (LOGIC-103)
---

В `ProjectData` Logic 12 прибавились записи, которых нет у 10.8.1 в том же проекте: глобальные MSeq и EvSq роли 0x17 с индексом `0x3C0000` и GenM роли 30 с индексом `0x140000`, он несёт JSON с состоянием Drummer (`genInstDrummerBaseModel.state`, четыре идентификатора дорожек, «Acoustic Drummer - Pop Rock»), хотя дорожек Drummer в проекте нет. Вместе с ним растёт Song (3 716 → 23 038 байт), AuCO (289 → 373), Trak (47 → 49), AuCU (7 → 9).

Trak имеет payload 94 байта вместо 93: добавлен один байт в конец, смысл не выяснен, поле `unknown`.

Продукт эти записи не использует: тест чтения на Spike Control даёт те же результаты. Предлагается записать как `single-sample`, смысл `unknown`.
