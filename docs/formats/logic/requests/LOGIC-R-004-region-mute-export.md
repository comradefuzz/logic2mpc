---
id: LOGIC-R-004
status: applied
kind: close-open
targets: LOGIC-046, LOGIC-090
proposed-status: confirmed
applies: Logic 10.8.1
evidence: Fuzz - Elated 1, `kick_nerve`: 9 выключенных регионов на тактах 89.25–92.75 и 96.75 и 2 выключенные папки отсутствуют в экспорте, соседние удары на месте
found-in: сессия кейса анализа Elated, 2026-10-31
created: 2026-10-31
resolved: 2026-10-31
---

Бит 0 по `+0x0c` подтверждён на реальном проекте с эталоном, поэтому LOGIC-046 можно поднять до `confirmed`.

В LOGIC-090 закрывается один пункт: Mute региона убирает его из Export All Tracks. Остальное в LOGIC-090 остаётся открытым: влияние эффектов и фейдеров, хвост, другие `Range`, Track Alternatives, take folders.

Наблюдение про эффекты, пока без вывода: `kick_nerve` в экспорте на 0.99 дБ громче исходника и не обнуляется (остаток −24 дБ), `clap_boys` и `snare_package` совпадают побитово. Это похоже на обработку канала бочки, в файле она пока не прочитана.
