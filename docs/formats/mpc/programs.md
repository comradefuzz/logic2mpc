# MPC: программы

### MPC-060 Пэды драм-программы
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, D01–D03
- fact: 128 записей `program.drum.instruments`, 16, 64 и 128 пэдов заполняются и загружаются, проверено на 63 разных файлах по кругу. У записи 8 слоёв `layersv`.
- updated: 2026-10-30

### MPC-061 Заполнение пэда
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T04; S-006, D01
- fact: На слой пишутся `sampleName`, `sampleFile`, `sliceInfo.End` (кадров минус один). Запись копируется из заполненного `instruments`.
- updated: 2026-10-30

### MPC-062 Нота пэда
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-004; S-006, D01
- fact: `program.padNoteMap.noteForPad`, пэд 0 это нота 36.
- updated: 2026-10-30

### MPC-063 Слои по скорости
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, V01
- fact: `velocityStart`, `velocityEnd` у слоя работают, два слоя на пэде чередуются по скорости.
- updated: 2026-10-30

### MPC-064 Кейгруппа из одного сэмпла
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, K01
- fact: Одна зона `instruments[0]`: `lowNote` 0, `highNote` 127, `layersv[0].rootNote` 0, `keyTrackEnable` false, `program.keygroup.numKeygroups` 1. Сэмпл играет по высотам.
- updated: 2026-10-30

### MPC-065 rootNote кейгруппы
- status: refuted
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, K02, K03: Live 2 показывает исходную ноту B0 у сэмпла G
- fact: `rootNote` 36 сбивает базу. `keyTrackEnable` при 36 разницы не дал, сочетание 0 и true не проверялось.
- superseded-by: MPC-064
- updated: 2026-10-30

### MPC-066 Полный состав с рабочей кейгруппой
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, в F01 у баса был `rootNote` 36
- fact: Состав HANDS, драм, кейгруппа, MIDI открылся и звучит, но полный состав с `rootNote` 0 не проверялся.
- updated: 2026-10-30

### MPC-067 Монофония
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, K04: аккорд; схема: K04 поставил `drum.monophonic` true при `drum.poliphony` 0 и зоне `polyphony` 0
- fact: Поля: `program.drum.monophonic`, `program.drum.poliphony` (написано так, 0 или 16), `instruments[].monophonic`, `instruments[].polyphony`, `monoRetrigger`, `legatoThreshold`. У пэдов драм-программ чаще пара true и 1, встречается false и 4, у кейгрупп false и 0. В K04 `polyphony` 1 не ставился, поэтому вопрос не закрыт.
- not: `monophonic` без `polyphony` 1 не сработал.
- updated: 2026-10-31

### MPC-068 Кейгруппа в примере
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-006, Rataklang - Brassic
- fact: `program.keygroup`, `program.samples`, зоны в `drum.instruments[N]` с `lowNote`, `highNote`. `layersv[].rootNote` равен 0, `keyTrackEnable` выключен, при этом сэмплы играют по высотам.
- updated: 2026-10-30

### MPC-069 Запись сэмпла программы
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T04; S-006, D01
- fact: Сэмпл добавляется в `samples` проекта и программы.
- updated: 2026-10-30

### MPC-070 Плагин
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T07, скопированный трек
- fact: `program.plugin.plugin.description` (имя, формат, `uid`) и закодированный `state`. Пресет Doom Drone сохраняется в `state` и возвращается при загрузке проекта.
- updated: 2026-10-30

### MPC-071 Пустой плагинный трек
- status: open
- applies: firmware 3.10.0.49
- evidence: S-005
- fact: Собирался только скопированный плагин, пустой плагинный трек не проверялся.
- updated: 2026-10-30

### MPC-072 MIDI-трек без инструмента
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, M01
- fact: Трек типа 4 с нотами и выходом `<none>` работает, после выбора порта звучит.
- updated: 2026-10-30

### MPC-073 Вес драм-программы
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-004, Rataklang - Brassic
- fact: Проект на 11 музыкальных треков плюс 28 служебных весит 17 МБ JSON, один драм-трек почти 3 МБ.
- updated: 2026-10-30

### MPC-074 Лимит слоёв
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, V01 проверял два слоя
- fact: Работа всех 8 слоёв на пэде не проверялась.
- updated: 2026-10-30

### MPC-075 Объект program
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 962 программ
- fact: Поля зависят от `type` (MPC-022). Полный список путей в [schema.tsv](schema.tsv).
- updated: 2026-10-31

| Поле | У каких типов | Смысл | Статус |
|---|---|---|---|
| `name`, `type`, `version` | все | | confirmed |
| `mixable` | все | Канал: `volume`, `pan`, `mute`, `solo`, `sends`, `inserts`, `audioRoute`, см. MPC-040, MPC-041 | hypothesis |
| `drum` | 0, 1 | Общий блок голосов, `instruments[]` | confirmed |
| `keygroup` | 1 | `numKeygroups` 1–5, `keygroupVersion` 13, `legacyMode` | confirmed |
| `padNoteMap` | все, кроме 6 | Карта пэд и нота, используется в типе 0 | confirmed |
| `samples` | все | Сэмплы программы, заполнены у 0 и 1 | confirmed |
| `plugin` | 3 | MPC-070 | single-sample |
| `midi` | 4 | Неизвестно | unknown |
| `audio` | 6 | `inputSource` 17, `monitorState` | single-sample |
| `programPads`, `customQLinks`, `fxRackQLinks`, `customisable`, `renderable`, `midiEventsFilter`, `chainID`, `transpose`, `midiKillGroup`, `customMacroSceneData`, `fxRackMacroSceneData` | все | Неизвестно | unknown |
| `xfaderRoute` | все, кроме 4 | Неизвестно | unknown |

### MPC-076 Объект instrument
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 6656 записей
- fact: `program.drum.instruments[]`: пэд драм-программы или зона кейгруппы.
- updated: 2026-10-31

| Поле | Значения | Смысл | Статус |
|---|---|---|---|
| `lowNote`, `highNote` | 0–127 | Диапазон зоны | confirmed |
| `layersv` | 8 | MPC-077 | confirmed |
| `monophonic`, `polyphony` | true и 1 у пэдов, false и 0 или 4 | См. MPC-067 | open |
| `mixable` | | Канал пэда | hypothesis |
| `coarseTune`, `fineTune`, `stretchPercentage`, `bpmLock`, `loopLock` | | Настройка и растяжение | hypothesis |
| `tempo` | 14 значений, 20–175 | Темп сэмпла | hypothesis |
| `randomPlaySeed` | 753 значения | Неизвестно | unknown |
| `muteTargets`, `simultPlayTargets`, `modLinks`, `synthSection`, `padEffects`, `chopProperties`, `articulations` | | Неизвестно | unknown |

### MPC-077 Объект layer
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 53 248 слоёв; S-006
- fact: `instruments[].layersv[]`.
- updated: 2026-10-31

| Поле | Значения | Смысл | Статус |
|---|---|---|---|
| `sampleName`, `sampleFile` | | Сэмпл | confirmed |
| `sliceInfo.Start`, `.End` | 0, кадры − 1 | Границы, кадры | confirmed |
| `sliceInfo.LoopStart`, `.LoopMode`, `.LoopCrossfadeLength`, `.LoopCrossfadeType`, `.NumLoopRepeats`, `.PulsePosition`, `.TailLength`, `.TailLoopPosition` | | Цикл и хвост | hypothesis |
| `velocityStart`, `velocityEnd` | 0–127 | Диапазон скорости | confirmed |
| `rootNote` | 0, 36 | 0 рабочее значение, см. MPC-064, MPC-065 | confirmed |
| `keyTrackEnable` | | Следование клавиатуре | single-sample |
| `coarseTune`, `pitch` | −4…7 | Сдвиг в полутонах, поля совпадают | hypothesis |
| `active`, `mute`, `pan`, `loop`, `offset`, `direction` | | Неизвестно, постоянные | unknown |
| `VolumeRandom`, `PanRandom`, `OffsetRandom`, `pitchRandom` | 0–0.47 | Случайный разброс | hypothesis |
| `oscillatorMode`, `OscillatorType`, `oscillatorParams` | `Warm Sine` | Осциллятор вместо сэмпла | hypothesis |

### MPC-123 Цвета пэдов драм-программы
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-015, S-025, `test-projects/reference/Example Colours.xpj`, наблюдения пользователя на Live 2, четыре снимка экрана Pad Color (`test-projects/reference/Pad Colour screens/`)
- fact: Цвет пэда хранится в `tracks[].program.programPads.pads.valueN` (N от 0 до 127 по порядку пэдов), целое RGB 0xRRGGBB, 0 значит цвет не задан. Пэд с сэмплом и незаданным цветом Live 2 показывает ярко-зелёным; совпадает с `universalPad` 0x00FF00 у новых треков, связь по файлу не доказана. Палитра PadColors из 25 цветов (в порядке, в котором пользователь красил пэды 0–24): 0xFF0000, 0xFF6D17, 0xFF4400, 0xFF8800, 0xECEC24, 0xFFD500, 0xE6FF00, 0xA2FF00, 0x55FF00, 0x11FF00, 0x00FF33, 0x00FF80, 0x00FFC4, 0x00F7FF, 0x00AAFF, 0x0066FF, 0xA2A9AD, 0x0022FF, 0x5200FF, 0x6F00FF, 0xB200FF, 0xFF00FF, 0xFF00BB, 0xFF0077, 0x29B574. Двадцать один совпадает с кругом цветов треков (MPC-122), три (0xFF6D17, 0xECEC24, 0xA2A9AD) это цвета служебных треков, 0x29B574 встречается только у пэдов.
- fact: Ключи `programPads` соответствуют экрану Pad Color по значениям эталона (прямой проверки сменой настройки не было): `Type` это PAD DISPLAY TYPE (0 Off, Classic Velocity, Fixed, Off->Velocity, Dim->Velocity, 5 Bright->Velocity; в эталоне 5), `UnusedPads` это EMPTY PADS (0 off, 1 dim, 2 normal; в эталоне 1), `Universal` это переключатель SINGLE PAD (false) и ALL PADS (true, у новых треков и в `Empty.xpj`) при цвете режима ALL PADS в `universalPad`, `PadsFollowTrackColour.value0` это режим FOLLOW TRACK (false в эталоне): по словам пользователя при нём цвета пэдов сбрасываются в цвет трека, заполненный пэд светится ярко, пустой приглушён. Как он соотносится с `tracks[].padsFollowTrackColour` (false везде), по файлу не видно. Что `pads.valueN` в режиме ALL PADS игнорируются, это вывод из поведения.
- fact: Нумерация по подписям экрана: банк B это B 01–B 16, B 01 слева внизу; согласуется с гипотезой MPC-R-002 (пэды 16–31 файла это B 01–B 16). Имена цветов палитры (например, `Canary`) кодам не сопоставлены.
- updated: 2026-11-08
