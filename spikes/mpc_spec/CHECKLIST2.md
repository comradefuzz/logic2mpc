# Чек-лист спайка 9, раунд 2

Один заход на Live 2. Скопируй на SD всю папку `test-projects/mpc/spike9b/`, имена не меняй. Открой каждый проект, запусти пэды и секвенцию, запиши результат. Это раунд 2: он ищет, какие постоянные поля пэда, слоя и события обязательны (в раунде 1 без всех постоянных полей `P04` молчал, а у `Q02` не было нот в гриде). Каждый кейс убирает одну группу полей. Всего 12.

| Проект | Что проверить | Результат |
|---|---|---|
| `B01 pad-version` | Пэды без поля `version`, остальное на месте: назначения пэдов, звук, уровни | |
| `B02 pad-no-tune` | Пэды без `coarseTune`, `fineTune`, `velocityScale`: звук, уровни | |
| `B03 pad-no-route` | Пэды без `layerCrossfade*` и `midiOut*`: звук, уровни | |
| `B04 pad-no-flags` | Пэды без `editAllLayers`, `ignoreBaseNote`, `bpmLock`, `loopLock`, `articulationUseXY`, `emulationProfile`, `partialPresetName`: звук, уровни | |
| `B05 pad-only-version` | Все постоянные поля пэда убраны, кроме `version`: назначения, звук, уровни | |
| `B06 layer-version` | Слои без поля `version`: назначения, звук | |
| `B07 layer-rest` | Слои без остальных постоянных полей, `version` на месте: назначения, звук | |
| `E01 event-version` | События без `version`: видны ли ноты в гриде, играют ли | |
| `E02 event-selected` | События без `selected`: видны ли ноты в гриде, играют ли | |
| `E03 note-version` | Ноты без `version`: видны ли ноты в гриде, играют ли | |
| `E04 note-modifiers` | Ноты без `modifierValue*` и `modifierActiveState*`: видны ли ноты, играют ли | |
| `E05 note-rest` | Ноты без `probability`, `ratchet`, `articulation`: видны ли ноты, играют ли | |

## Готово

Пришли таблицу.
