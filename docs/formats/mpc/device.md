# MPC: поведение Live 2

### MPC-100 Обозначение нот
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T06
- fact: Нота 60 показана на Live 2 как C3.
- updated: 2026-10-30

### MPC-101 Повторное открытие
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T10 resaved
- fact: Пересохранённый собранный проект открывается заново, треки, ноты, темп, пресет и выход на устройство сохраняются.
- updated: 2026-10-30

### MPC-102 Сортировка samples
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, сравнение T10 full и T10 resaved
- fact: При сохранении Live 2 сортирует `samples` по имени в проекте и программах, `metadata.tempo` у сэмпла меняется с 175.0 на 175.00001525878907.
- updated: 2026-10-30

### MPC-103 clipPlayerData
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, в сборке карта осталась от шаблона, проект открылся
- fact: При сохранении Live 2 пересобирает `clipPlayerData.trackClipTransportMap`, синхронизировать её в сборке не нужно.
- updated: 2026-10-30

### MPC-104 Поля состояния
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T10 resaved
- fact: При сохранении меняются `currentTrackIndex`, `engineMode`, `tracks[].recordArm`.
- updated: 2026-10-30

### MPC-105 deviceId порта
- status: hypothesis
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, `deviceId` с `28-1` на `24-1`, имя осталось
- fact: Вероятно, устройство ищется по имени, а `deviceId` обновляется при сохранении.
- updated: 2026-10-30

### MPC-106 Нормализация служебных полей
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T10 resaved
- fact: `sliceInfo.LoopCrossfadeLength` с 0 на -1, индексы, `behaviour` и `track` в QLink.
- updated: 2026-10-30

### MPC-107 Окно SAVE
- status: single-sample
- applies: firmware 3.10, драм-трек
- evidence: S-004, снимок пользователя
- fact: `Project`, `Project As`, `New Project`, `Track`, `Track FX Rack`, `Drum Program`, `Sample`, `Track as Audio`, `Track as MIDI/Pattern`, `All Tracks`, `Audio Mixdown`, `Ableton Live Set`, `Drum Pads as Stems`, `Drum Track as MPC Sample file`. На других типах список может отличаться.
- updated: 2026-10-30

### MPC-108 Загрузка поштучно
- status: open
- applies: firmware 3.10.0.49
- evidence: S-004, снято решением пользователя
- fact: Загрузка программ и MIDI поштучно не проверялась, проверенного запасного выхода нет.
- updated: 2026-10-30

### MPC-109 originalCreatorProductIdentifier
- status: open
- applies: firmware 3.10.0.49
- evidence: S-004
- fact: Значение `ACVB`, что это за продукт, неизвестно.
- updated: 2026-10-30

### MPC-110 Пустой проект Live 2
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-004, S-015, test-projects/reference/Empty.xpj; неудаляемость служебных треков со слов пользователя
- fact: Пустой проект Live 2 содержит 29 треков: `Drum 001` (тип 0, `recordArm` true) и 28 служебных (Out, Submix, Return). Секвенций и сэмплов нет, `currentTrackIndex` 0. Клипы живут только в `sequences[]`, поэтому у проекта без секвенций нет и клипов. Служебные треки удалить на Live 2 нельзя. Для открытия они не обязательны (снято MPC-112).
- updated: 2026-11-06

### MPC-111 recordArm
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-003, разбор пэдов Elated; `Rataklang - Brassic.xpj`, `T10 resaved.xpj`; подтверждено пользователем
- fact: `tracks[].recordArm` true значит, что игра на пэдах идёт в этот трек. В собранном Elated true стоял у всех 8 музыкальных треков, и пэд запускал сэмпл на всех дорожках сразу. На воспроизведение секвенции поле не влияет. Live 2 при сохранении оставляет true только у `currentTrackIndex` (MPC-104). Копия трека наследует поле. Сборка с одним true проверена не была.
- updated: 2026-11-06

### MPC-112 Проект без служебных треков
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-005, S-015, кейсы Z01–Z03, по одному открытию каждого
- fact: Проект без служебных треков Out, Submix, Return (вместе, без Out, без Submix и Return) открывается на Live 2, звучит, сэмпл в нём можно добавить. Отсутствующие треки Live 2 не пересоздаёт: в проекте без Submix и Return в MIX остаются `Drum 001` и OUT 1/2–7/8, добавить сабмиксы и ретурны из интерфейса неясно как. Для открытия служебные треки не обязательны (уточняет MPC-110).
- updated: 2026-11-06

### MPC-113 Минимальный корень проекта
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-006, S-015, кейсы R01–R06 на основе Empty.xpj, по одному открытию каждого
- fact: Live 2 открывает проект с корнем из `version`, `key`, `masterTempoEnabled`, `masterTempo`, `samples`, `tracks`, `sequences`, `currentTrackIndex`, `currentSequence`, `engineMode`. По отдельности можно убрать `mixer` (микшер работает штатно), `scene`, `songs` (Song Mode пуст), `assignable*`, `qlink*`, `rowLaunch*`, `midiLearn*`, `parameterSnapshotter*`, `gui*`, `tui*` и клип-матрицы. Образец один, звук проверялся не во всех кейсах.
- updated: 2026-11-06

### MPC-114 Минимальный драм-трек
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-007, S-015, кейсы T01–T04 на основе Empty.xpj, по одному открытию каждого
- fact: Драм-трек открывается и работает без постоянных полей трека и программы по реестру, без `colour` (цвет голубой) и без `program.mixable` (громкость трека и пэдов работает). При выключенном `recordArm` у единственного драм-трека пэды срабатывают. При нескольких драм-треках не проверялось (см. MPC-111).
- updated: 2026-11-06

### MPC-115 Поведение пэда
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-008, S-015, кейсы P01–P06 на основе D01 pads16, по одному открытию каждого
- fact: `triggerMode` 0 это Sample Play One Shot, 2 это Note On (играет по длительности ноты). `monophonic` false при `polyphony` 1: повторные удары не обрывают звук; при `polyphony` 4 полифония работает (Poly 4). `warpEnable` true включает варп (слышны артефакты). `whichMuteGroup` 1 даёт Mute Group 1, один пэд глушит другой. Если у пэдов убрать постоянные поля, назначения на пэдах пропадают, после ручного назначения уровни равны нулю, звука нет. Значения по умолчанию Live 2 не равны постоянным значениям образцов. Какие поля нужны, выяснено в MPC-117: только `version`.
- updated: 2026-11-06

### MPC-116 Минимальные клип, событие, сэмпл, секвенция, MIDI-трек
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-009, S-015, кейсы Q01–Q04 и M01, по одному открытию каждого
- fact: Без постоянных полей по реестру Live 2 открывает и проигрывает клип, запись сэмпла, секвенцию и MIDI-трек. Событие-нота без постоянных полей не появляется в гриде (пэды вручную работают), значит часть постоянных полей события обязательна, какая именно, выяснено в MPC-118: `events[].version`.
- updated: 2026-11-06

### MPC-117 Обязательное поле пэда
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-010, S-015, раунд 2, кейсы B01–B07, по одному открытию каждого
- fact: Из постоянных полей пэда обязательно только `instruments[].version`: без него сэмплы остаются в пуле проекта и не назначаются на пэды. Остальные постоянные поля пэда (`coarseTune`, `fineTune`, `velocityScale`, `layerCrossfade*`, `midiOut*`, флаги) и постоянные поля слоя (включая `layersv[].version`) можно не писать: звук есть, ноты играют. Уточняет MPC-115.
- updated: 2026-11-06

### MPC-118 Обязательное поле события
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-011, S-015, раунд 2, кейсы E01–E05, по одному открытию каждого
- fact: Из постоянных полей события-ноты обязательно только `events[].version`: без него нот в гриде нет. Без `selected`, `note.version`, `note.modifier*`, `note.probability`, `note.ratchet`, `note.articulation` ноты есть и играют. Уточняет MPC-116.
- updated: 2026-11-06

### MPC-122 Цвет нового драм-трека и служебных треков
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-014, S-025, `test-projects/reference/Example Colours.xpj` (64 драм-трека созданы подряд, сохранён Live 2)
- fact: Live 2 назначает новому драм-треку `tracks[].colour` (целое RGB 0xRRGGBB) по кругу из 21 значения: 0x55FF00, 0x00FF80, 0x00AAFF, 0x5200FF, 0xFF00FF, 0xFF4400, 0xE6FF00, 0x11FF00, 0x00FFC4, 0x0066FF, 0x6F00FF, 0xFF00BB, 0xFF8800, 0xA2FF00, 0x00FF33, 0x00F7FF, 0x0022FF, 0xB200FF, 0xFF0077, 0xFF0000, 0xFFD500. Первый трек получает 0x55FF00, 22-й снова 0x55FF00. Служебные треки красятся фиксированно: Submix 0xFF6D17, Return 0xECEC24, Out 0xA2A9AD. `padsFollowTrackColour` false у всех 92 треков образца. Голубой по умолчанию из MPC-114 (0x0022FF) это 17-й цвет круга. Порядок показал один проект.
- updated: 2026-11-08

### MPC-124 Число mute group драм-программы
- status: single-sample
- applies: firmware 3.10.0.49, Live 2
- evidence: MPC-R-013, S-024, наблюдение пользователя на Live 2 (в драм-программе доступно 32 mute group); значение 1 у двух пэдов даёт общую группу (MPC-115, кейс P06)
- fact: `whichMuteGroup` пэда драм-программы принимает 0 (нет группы) и 1–32, группы действуют внутри программы. В файлах-образцах встречались только 0, 1 и 2, значения выше 2 в проектах не наблюдались, три и больше групп в одной программе на устройстве не проверялись.
- updated: 2026-11-08
