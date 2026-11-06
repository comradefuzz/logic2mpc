---
id: MPC-R-006
status: applied
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: S-015, раунд 1, кейсы R01–R06 (`test-projects/mpc/spike9/`, основа `reference/Empty.xpj`), открыты на Live 2 пользователем. R01 без `mixer`: открылся, работает штатно. R02 без `scene`, R04 без `assignable*`, `qlink*`, `rowLaunch*`, `midiLearn*`, `parameterSnapshotter*`, R05 без `gui*`, `tui*` и клип-матриц: открылись, всё в порядке. R03 без `songs`: открылся, Song Mode пуст, как и ожидалось. R06 минимальный корень: открылся
found-in: S-015
created: 2026-11-06
resolved: 2026-11-06
comment: Принят по прямому наблюдению пользователя на Live 2; номер MPC-113.
---

Предлагается записать как `single-sample`: на Live 2 открывается проект, у которого в корне `data` оставлены только `version`, `key`, `masterTempoEnabled`, `masterTempo`, `samples`, `tracks`, `sequences`, `currentTrackIndex`, `currentSequence`, `engineMode`. Каждый из блоков `mixer`, `scene`, `songs`, группы `assignable*`, `qlink*`, `rowLaunch*`, `midiLearn*`, `parameterSnapshotter*` и состояние интерфейса можно убрать и по отдельности. Образец один (Empty.xpj, треки включают служебные), кейс R06 проверен однократно, звук и работа микшера проверялись только для R01.
