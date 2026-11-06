---
id: MPC-R-010
status: applied
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: S-015, раунд 2, кейсы B01–B07 (`test-projects/mpc/spike9b/`, основа `spike7/D01 pads16`), открыты на Live 2 пользователем. B01 пэды без `version`: сэмплы в проекте, на пэды не назначены. B02 без `coarseTune`, `fineTune`, `velocityScale`, B03 без `layerCrossfade*` и `midiOut*`, B04 без флагов (`editAllLayers`, `ignoreBaseNote`, `bpmLock`, `loopLock`, `articulationUseXY`, `emulationProfile`, `partialPresetName`), B05 без всех постоянных полей пэда кроме `version`, B06 слои без `version`, B07 слои без остальных постоянных полей: во всех звуки есть, ноты играются, разницы с исходным нет
found-in: S-015
created: 2026-11-06
resolved: 2026-11-06
comment: Принят по прямому наблюдению пользователя на Live 2; номер MPC-117.
---

Предлагается записать как `single-sample`: из постоянных полей пэда драм-программы обязательно только `instruments[].version`. Без него Live 2 открывает проект, но не назначает сэмплы на пэды (они остаются в пуле проекта). Остальные постоянные поля пэда и все постоянные поля слоя (в том числе `layersv[].version`) можно не писать: пэды звучат и играют ноты. Это объясняет кейс P04 раунда 1, где `version` убирался вместе с остальным. Образец один на кейс.
