# Logic: дорожки и стеки

### LOGIC-020 Порядок дорожек
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: Порядок строк даёт `karT` с `idx` 0x40000 и ссылкой 2 равной 0: номер строки это ссылка 1, слот канала в `pay+0x08`.
- updated: 2026-10-30

### LOGIC-021 Имена дорожек
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: Имена берутся из `ivnE`: размерная строка в `pay+0x9E`, вид объекта в `pay+0x5A`, канал `idx >> 16`.
- not: Смещение имени в `karT` из спецификации LogicProFormatWriter не подошло.
- updated: 2026-10-30

### LOGIC-022 Строка Stereo Out
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: В списке на одну строку больше `NumberOfTracks`: это Stereo Out с типом строки 3, она отбрасывается.
- updated: 2026-10-30

### LOGIC-023 Глубина стека
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, деревья Pyro и Elated сверены с экраном Logic
- fact: Глубина вложенности в `karT pay+0x0e`. Строка это заголовок стека, если следующая строка глубже.
- updated: 2026-10-30

### LOGIC-024 Тип стека
- status: single-sample
- applies: Logic 10.8.1
- evidence: S-001, один folder-стек в копии контрольного проекта
- fact: Бит 0x40 в `karT pay+0x28`: установлен у summing, снят у folder. Во всех реальных проектах вышло summing, это не проверено.
- not: Значение `0xa0` не признак заголовка: оно встречается у обычной дорожки `Audio 74` в Pyro.
- updated: 2026-10-30

### LOGIC-025 Mute дорожки
- status: open
- applies: Logic 10.8.1
- evidence: S-002, `probe.py` не читает
- fact: Где в файле хранится Mute дорожки, не выяснено.
- updated: 2026-10-30

### LOGIC-026 Track Alternatives
- status: open
- applies: Logic 10.7.0
- evidence: S-001, MONTERO
- fact: В MONTERO 37 списков `0xc0000` и 838 размещений вне основного обхода, все под записью `Track Alternatives`. Вероятно, это неактивные версии дорожек. Не прочитаны, партии можно потерять.
- updated: 2026-10-30

### LOGIC-027 Повтор имён дорожек
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, Pyro: три `GTR L`, два `Glitch`
- fact: Имена дорожек могут повторяться, идентификатор это номер строки, а не имя.
- updated: 2026-10-30

### LOGIC-028 Стек глубже двух уровней
- status: open
- applies: Logic 10.8.1
- evidence: S-002
- fact: Правила нумерации и файлов стеков глубже двух уровней не проверялись.
- updated: 2026-10-30

### LOGIC-019 Запись Trak
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: перепись 3511 записей `pd_layout.py karT`; смысл полей S-001
- fact: Строка дорожки. Основной список: индекс 0x40000, ссылка 2 равна 0. Payload 0 байт у 1692 записей: их роль неизвестна.
- updated: 2026-10-31

| Смещение | Тип | Значения | Смысл | Статус |
|---|---|---|---|---|
| +0x00 | u8 | 1, 3, 6 | Тип строки: 3 Stereo Out, остальные неизвестны | single-sample |
| +0x01 | u8 | 0, 1, 3 | Неизвестно | unknown |
| +0x02 | u16 | 6 значений: 0x14, 0x814, 0, 1 и другие | Неизвестно | unknown |
| +0x04 | u32 | чаще 0 | Неизвестно | unknown |
| +0x08 | u32 | кратно 4 | Слот канала, ключ к Envi | confirmed |
| +0x0C | u16 | 6 значений, чаще 0 | Неизвестно | unknown |
| +0x0E | u16 | 0, 1, 2 | Глубина вложенности | confirmed |
| +0x10–0x17 | | 0 | Постоянные | unknown |
| +0x18 | 16 байт | у каждой строки свои | Вероятно, UUID дорожки | hypothesis |
| +0x28 | u16 | биты | Бит 0x40 summing-стек | single-sample |
| +0x2A | u16 | чаще 0x0010, 0x0C10, 6 значений | Неизвестно | unknown |
| +0x2C | u16 | 0, 0x8000, 0x0100, 0x0F00 | Неизвестно | unknown |
| +0x2E | u16 | 22 значения, чаще 0 | Неизвестно | unknown |
| +0x30 | u16 | 0 | Постоянное | unknown |
| +0x32 | u16 | 5 значений, чаще 0 | Неизвестно | unknown |
| +0x34 | u32 | 0, 0xFFFFFFFF, другие | Неизвестно | unknown |
| +0x38 | u8 | только у записей 57 байт | Неизвестно | unknown |

### LOGIC-029 Запись Envi
- status: single-sample
- applies: Logic 10.7.0, 10.8.1
- evidence: перепись 776 записей, смысл полей S-001, остальное в [layouts.txt](layouts.txt)
- fact: Канал окружения, размер 178–2290 байт. Индекс заголовка, сдвинутый на 16, это номер канала, на него ссылается Trak.
- updated: 2026-10-31

| Смещение | Тип | Значения | Смысл | Статус |
|---|---|---|---|---|
| +0x00 | u16 | 0x06D0, 0x06A0, 0x02E8 | Неизвестно, то же значение почти всегда в `+0x72` | unknown |
| +0x10 | u16 | кратно 4 | Неизвестно | unknown |
| +0x2C | u16 | 0x0301, 1, 0x0201, 0x0101 | Неизвестно | unknown |
| +0x50–0x58 | u16 | | Неизвестно | unknown |
| +0x5A | u8 | | Вид объекта окружения | confirmed |
| +0x74 | строка | редко | Вероятно, имя инструмента | hypothesis |
| +0x9E | u16 и строка | | Имя канала | confirmed |
