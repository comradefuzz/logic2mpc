# MPC: контейнер

### MPC-001 Файл .xpj
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, Rataklang - Brassic, Spike4 A и B
- fact: Gzip: пять строк заголовка (`ACVS`, версия, `SerialisableProjectData`, `json`, `Linux`), затем JSON с корнем `data`, версия данных 30.
- updated: 2026-10-30

### MPC-002 Файл .xpm
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, Spike 4 Drum
- fact: Тот же gzip с заголовком `SerialisableProgramData`, JSON. Форматирование отличается от `.xpj`. Сэмплы лежат рядом в `<имя>_[ProgramData]`.
- updated: 2026-10-30

### MPC-003 Программа в проекте
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, сравнение Spike 4 Drum и Spike4 A
- fact: Содержимое `.xpm` равно `tracks[0].program` из `.xpj`, отличается только `name`.
- updated: 2026-10-30

### MPC-004 Заголовок gzip
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-005, все собранные файлы повторяли его
- fact: Файлы Live 2 начинаются с `1f 8b 08 00 00 00 00 00 00 03`. Важен ли он, не проверялось.
- updated: 2026-10-30

### MPC-005 Числа JSON
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-005, `patch.py` повторяет JSON побайтно на трёх проектах
- fact: Live 2 пишет float с 17 знаками, стандартный json их округляет. Числа надо хранить текстом, чтобы не менять чужие значения. Необходимо ли это Live 2, не проверялось.
- updated: 2026-10-30

### MPC-006 Контрольная сумма
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-005, T02–T10 открылись на Live 2
- fact: Изменённый JSON принимается: контрольная сумма либо отсутствует, либо не проверяется.
- updated: 2026-10-30

### MPC-007 Clone-and-patch
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-005, T01–T10; S-006, D01–D03, K01, M01, S01, S02, V01
- fact: Проект собирается из шаблона с Live 2 правкой JSON и копированием сэмплов. Служебные поля `mixer` и `scene` не менялись. Плагин пока копируется из проекта-донора.
- updated: 2026-10-30

### MPC-008 Обязательные поля
- status: open
- applies: firmware 3.10.0.49
- evidence: S-005
- fact: Какие поля обязательны, неизвестно: служебные оставались от шаблона. Не проверялись порядок ключей и форматирование. Точно необязательна синхронизация `trackClipTransportMap` (MPC-103).
- updated: 2026-10-30

### MPC-009 Корень data
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 32 проектов, 3122 пути, [schema.tsv](schema.tsv)
- fact: Группы полей. Музыка: `version`, `key`, `masterTempo`, `masterTempoEnabled`, `samples`, `tracks`, `sequences`, `songs`, `locators`, `trackMutePerSequence`. Сведение: `mixer`, `scene`, `sharedClipMatrixData`, `clipPlayerData`. Управление: `qlink*`, `assignable*`, `midiLearnSettings`, `padPerformSettings`, `arpeggiatorProperties`, `quantiser`, `xyfxResponder`. Состояние интерфейса: `current*`, `engineMode`, `tui*`, `gui*`, `mpc*`, `horizontalClipMatrixView`. Метаданные: `info`, `lastSavedProductIdentifier`, `originalCreatorProductIdentifier`.
- updated: 2026-10-31
