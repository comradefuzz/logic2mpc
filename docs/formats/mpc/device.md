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
