# MPC: сэмплы

### MPC-080 Папка сэмплов
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-004, S-005
- fact: Сэмплы лежат рядом с проектом в `<имя>_[ProjectData]`, `samples[].path` это имя файла в папке.
- updated: 2026-10-30

### MPC-081 Имя файла и папки
- status: open
- applies: firmware 3.10.0.49
- evidence: S-005, всегда совпадали
- fact: Несовпадение не проверялось и не проверяется: они совпадают всегда. Имя проекта может отличаться от шаблона.
- updated: 2026-10-30

### MPC-082 Форматы
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, A01, A02
- fact: Длинный луп, WAV 24 бита 48 кГц стерео и моно загружаются. В примерах встречается 32-битный float, длина кадров берётся из заголовка RIFF.
- updated: 2026-10-30

### MPC-083 Отсутствующий сэмпл
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, E01
- fact: Если файла нет, Live 2 показывает `Sample not found` с вариантами `Abort` и `Resolve`.
- updated: 2026-10-30

### MPC-084 Кириллица в именах
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, снято: кириллица всегда транслитерируется
- fact: Поведение Live 2 на кириллице не проверялось.
- updated: 2026-10-30

### MPC-085 Запись sample
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 283 записей
- fact: `samples[]` версии 1: `name`, `path`, `loadImpl` 0 или 1, `metadata.key`, `metadata.rootNote` 36–84, `metadata.tempo`, `metadata.tune`. Смысл `loadImpl` неизвестен.
- updated: 2026-10-31
