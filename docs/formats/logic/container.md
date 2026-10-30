# Logic: контейнер

### LOGIC-001 Пакет .logicx
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: S-001, Pyro и MONTERO
- fact: `.logicx` это папка-пакет: `Resources/ProjectInformation.plist`, `Media/`, `Alternatives/NNN/`.
- updated: 2026-10-30

### LOGIC-002 Содержимое альтернативы
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: S-001, Pyro и MONTERO
- fact: В `Alternatives/NNN/` лежат `MetaData.plist`, `DisplayState.plist`, `DisplayStateArchive`, `ProjectData`, `WindowImage.jpg`, `Project File Backups/`, `Undo Data.nosync/`.
- updated: 2026-10-30

### LOGIC-003 Номера альтернатив
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: S-001, Pyro `000`, MONTERO `002`
- fact: Номера альтернатив могут начинаться не с нуля, первую папку нельзя считать `000`.
- updated: 2026-10-30

### LOGIC-004 Активная альтернатива
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: Активная альтернатива записана в ключе `ActiveVariant` файла `ProjectInformation.plist`. В проектах с одной альтернативой (Pyro, Elated) ключа нет.
- updated: 2026-10-30

### LOGIC-005 Основные параметры в MetaData.plist
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: `MetaData.plist` читается штатно и даёт `BeatsPerMinute`, `SongSignatureNumerator`, `SongSignatureDenominator`, `NumberOfTracks`, `AudioFiles`, `UnusedAudioFiles`, `SamplerInstrumentsFiles`. Смен темпа и размера в нём нет.
- updated: 2026-10-30

### LOGIC-006 Тональность и частота
- status: single-sample
- applies: Logic 10.8.1
- evidence: S-001, значения читаются, эталона нет
- fact: `SongKey`, `SongGenderKey`, `SampleRate` в `MetaData.plist`.
- updated: 2026-10-30

### LOGIC-007 Заголовок файла ProjectData
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: перепись 21 файла, `spikes/format_re/pd_layout.py`
- fact: 24 байта, little-endian, дальше записи подряд до конца файла.
- updated: 2026-10-31

| Смещение | Тип | Значение | Смысл | Статус |
|---|---|---|---|---|
| 0x00 | 4 байта | `23 47 C0 AB` | Сигнатура | confirmed |
| 0x04 | u16 | 0x09CB, 0x09C4 | Версия файла, повторена в Song `+0x04`. 0x09C4 только в MONTERO | single-sample |
| 0x06 | u16 | 3 | Неизвестно, постоянное | unknown |
| 0x08 | u32 | 4 | Неизвестно, постоянное | unknown |
| 0x0C | u16 | 1 | Неизвестно, постоянное | unknown |
| 0x0E | u16 | 8 | Неизвестно, постоянное | unknown |
| 0x10 | u32 | размер файла − 24 | Длина всех записей | confirmed |
| 0x14 | u32 | 0 | Неизвестно, постоянное | unknown |

### LOGIC-008 Заголовок записи
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: 25 714 записей в 21 файле, все файлы пройдены до конца
- fact: 36 байт перед payload.
- updated: 2026-10-31

| Смещение | Тип | Значение | Смысл | Статус |
|---|---|---|---|---|
| 0x00 | 4 байта | ASCII | Тег, слово записано задом наперёд: `karT` это `Trak` | confirmed |
| 0x04 | u8 | 1, 2, 4, 5 и другие | Неизвестно | unknown |
| 0x05 | u8 | 0 | Неизвестно, постоянное | unknown |
| 0x06 | u16 | см. LOGIC-009 | Роль, вид записи внутри тега. `0xFFFF` у Song | confirmed |
| 0x08 | u32 | старшие 16 бит это номер, младшие 0 | Индекс записи. `0xFFFFFFFF` у Song | confirmed |
| 0x0C | u32 | | Второй индекс: AuRg адресуется парой индекс и это поле | confirmed |
| 0x10 | u16 | 0 или 0xFFFF | Неизвестно | unknown |
| 0x12 | u16 | | Ссылка 1. У Trak это номер строки дорожки | confirmed |
| 0x14 | u16 | | Ссылка 2, смысл зависит от тега | single-sample |
| 0x16 | u16 | 2 | Неизвестно, постоянное | unknown |
| 0x18 | u16 | 0 | Неизвестно, постоянное | unknown |
| 0x1A | u16 | 1 | Неизвестно, постоянное | unknown |
| 0x1C | u32 | | Размер payload | confirmed |
| 0x20 | u32 | 0 | Неизвестно, постоянное | unknown |

### LOGIC-009 Каталог тегов
- status: confirmed
- applies: Logic 10.7.0, 10.8.1
- evidence: перепись 21 файла; смысл из S-001, S-003 там, где он указан
- fact: 27 тегов. Перепись по ролям и размерам: [records.txt](records.txt), побайтовая разметка заголовка и всех тегов: [layouts.txt](layouts.txt). Payload показан до 8192 байт, длиннее только GenM, AuCU, SngO и EvSq.
- updated: 2026-10-31

| Тег | Слово | Роль | Записей | Размер payload | Смысл | Статус |
|---|---|---|---|---|---|---|
| `gnoS` | Song | 0xFFFF | 21 | 3716 | Настройки проекта, одна на файл, LOGIC-018 | single-sample |
| `karT` | Trak | 0x17 | 3511 | 0, 56, 57 | Строка дорожки, LOGIC-019 | confirmed |
| `ivnE` | Envi | 0x14 | 776 | 178–2290 | Канал окружения, LOGIC-021 | confirmed |
| `qeSM` | MSeq | 1, 3, 5, 0xE, 0x16, 0x17, 0x19 | 1692 | 296–352 | Заголовок последовательности, LOGIC-059 | confirmed |
| `qSvE` | EvSq | те же | 1692 | 16–298176 | События последовательности, парная к MSeq по роли и индексу | confirmed |
| `qSxT` | TxSq | 0x20 | 244 | 100–566 | Текст, в том числе RTF маркеров | confirmed |
| `gRuA` | AuRg | 0xB | 2849 | 204–278 | Аудиорегион, LOGIC-039 | confirmed |
| `lFuA` | AuFl | 0xB | 499 | 598–742 | Аудиофайл, LOGIC-038 | confirmed |
| `tSxT` | TxSt | 4 | 672 | 142–154 | Вероятно, стиль текста | hypothesis |
| `lytS` | Styl | 0xC | 672 | 100–270 | Вероятно, стиль | hypothesis |
| `OCuA` | AuCO | 0xE | 7093 | 14–264 | Неизвестно, префикс Au | unknown |
| `UCuA` | AuCU | 0xE | 2559 | 44–3028192 | Вероятно, состояние Audio Unit: самые большие записи | hypothesis |
| `nCuA` | AuCn | 0xE | 273 | 132–4016 | Неизвестно | unknown |
| `vEuA` | AuEv | 0 | 58 | 52 | Неизвестно | unknown |
| `MneG` | GenM | 0x1E | 1633 | 38–10860 | Неизвестно | unknown |
| `OgnS` | SngO | 0xE | 46 | 1206–716626 | Неизвестно | unknown |
| `tScS` | ScSt | 0xE | 21 | 3752 | Неизвестно, одна на файл | unknown |
| `tSnI` | InSt | 2 | 21 | 64 | Неизвестно, одна на файл | unknown |
| `ryaL` | Layr | 0xE | 21 | 228 | Неизвестно, одна на файл | unknown |
| `ediV` | Vide | 0xE | 21 | 130 | Неизвестно, одна на файл | unknown |
| `rpyH` | Hypr | 0xF | 63 | 200–6194 | Неизвестно, три на файл | unknown |
| `MroC` | CorM | 0xE | 42 | 106–406 | Неизвестно, две на файл | unknown |
| `snrT` | Trns | 0xA | 3 | 492 | Неизвестно, только Pyro, Elated, MONTERO | unknown |
| `ddAG` | GAdd | 0x22 | 1224 | 5–20 | Неизвестно, только Pyro | unknown |
| `dirG` | Grid | 0x22 | 1 | 36 | Неизвестно, только Pyro | unknown |
| `pilC` | Clip | 7 | 6 | 85 | Неизвестно | unknown |
| `dlFA` | AFld | 0xE | 1 | 3430 | Неизвестно, только MONTERO | unknown |

### LOGIC-010 Разрешение времени
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-003, 960 против 480 PPQ в MIDI-экспорте, длины отличаются на тик округления
- fact: Внутреннее разрешение 960 тиков на четверть.
- updated: 2026-10-30

### LOGIC-011 Начало отсчёта
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: Позиции в карте темпа, маркерах и нотах отсчитываются от 38400 тиков, размещения регионов от 34560.
- updated: 2026-10-30

### LOGIC-012 Неизвестная версия файла
- status: confirmed
- applies: любая версия
- evidence: S-001, размер записей и номера схем менялись между версиями
- fact: Формат недокументирован, чтение привязывается к версии файла. На неизвестной версии чтение останавливается с сообщением, а не выдаёт догадку.
- updated: 2026-10-30

### LOGIC-018 Запись Song
- status: single-sample
- applies: Logic 10.7.0, 10.8.1
- evidence: перепись 21 записи, [layouts.txt](layouts.txt)
- fact: Одна на файл, 3716 байт. Из полей известно только `+0x04` версия файла, остальные 3714 байт не разобраны, их значения перечислены в приложении.
- updated: 2026-10-31
