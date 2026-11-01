---
id: LOGIC-R-006
status: applied
kind: close-open
targets: LOGIC-051
proposed-status: single-sample
applies: Logic 10.8.1
evidence: S-008, `Lothar BM` в Elated 1: регион на такте 41, длина 8, `+0x1c` 14 тактов; из 11 нот второго прохода читаются 9, последняя кончается на 54.99, RMS моно по четвертям такта: −11.8 до такта 55, затем −28, −38.5, −49.5, −59.6, новых нот нет
found-in: S-008
created: 2026-10-31
resolved: 2026-10-31
---

Обрезанный Loop подчиняется LOGIC-047: проход обрывается на начале региона плюс `+0x1c`, ноты с началом за этой границей не звучат.

Предлагается перевести LOGIC-051 в `single-sample`: сверен один регион. `FSS_S2DC_BASS_Delta` в Pyro не проверялся, экспорта Pyro нет.
