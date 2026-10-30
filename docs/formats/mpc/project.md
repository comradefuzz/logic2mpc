# MPC: проект

### MPC-020 Состав пустого проекта
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-004, Spike4 A
- fact: Проект с одним драм-треком содержит 29 треков: 1 драм, 8 Submix, 4 Return, 16 Out.
- updated: 2026-10-30

### MPC-021 Трек
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, S-005
- fact: `tracks[]` с полями `name`, `mute`, `program`, включая Submix, Return и Out.
- updated: 2026-10-30

### MPC-022 Тип программы
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-004, выведено по именам треков
- fact: `program.type`: 0 драм, 1 кейгруппа, 3 плагин, 4 MIDI, 6 аудио, 7 Return, 8 Submix, 9 Out.
- updated: 2026-10-30

### MPC-023 Вставка трека
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-005, T05, T10; S-006, S02
- fact: Трек вставляется перед служебными, запись о нём добавляется в `trackClipMaps` каждой секвенции. Работает при нескольких секвенциях.
- updated: 2026-10-30

### MPC-024 Клипы
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, S-005
- fact: `sequences[].value.trackClipMaps[][]`: ключ это имя трека, список отсортирован по имени, в значении `startPulses`, `endPulses`, `loop`, `eventList`.
- updated: 2026-10-30

### MPC-025 Нота
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004, сдвиг на долю меняет одно поле с 0 на 960; S-005, T03
- fact: Событие `type: 3`: `time`, `note.note`, `note.velocity` 0–1, `note.length`, время в тиках, 960 на четверть. Новая нота копируется из существующего события.
- updated: 2026-10-30

### MPC-026 Автоматизация
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-004, один проект
- fact: Событие `type: 1`, поле `automation`: `note`, `value`, `parameter`. Смысл параметров не выяснен.
- updated: 2026-10-30

### MPC-027 Секвенция
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-004; S-006, S01
- fact: `sequences[].value`: `name`, `bpm`, `lengthBars`, `timeSignatureTrack`, разрешение `beatLength` 960. Две секвенции работают.
- updated: 2026-10-30

### MPC-028 Темп
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: S-005, T09 темп 97
- fact: `masterTempo`, `masterTempoEnabled`. В примере 95 при `bpm` 120 в секвенциях.
- updated: 2026-10-30

### MPC-029 Смена темпа внутри песни
- status: open
- applies: firmware 3.10.0.49
- evidence: схема 39 секвенций, во всех `seqEventList.events` пуст
- fact: Кандидаты: `sequences[].value.tempoEnable` и `seqEventList` со своими `length`, `numFilterTypes` 32, `quantisation`. Вид события неизвестен: образца со сменой нет.
- updated: 2026-10-31

### MPC-030 Смена размера
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, S03; схема
- fact: Размер хранится дважды: `sequences[].value.timeSignatureTrack.timeSignatures[]` и `value.trackClipMaps[][].value.timeSignatureList.timeSignatures[]`, поля `barStart`, `beatLength`, `beatsPerBar`. S03 менял только первый список, у клипов `barStart` везде 0.
- not: Запись только в `timeSignatureTrack` не работает.
- updated: 2026-10-31

### MPC-031 Song Mode
- status: open
- applies: firmware 3.10.0.49
- evidence: схема, 32 проекта
- fact: `songs[]` всегда 32 слота: `name` `(unnamed)`, `ignoreTempo`, `items`. Вид элемента `items` неизвестен: образца нет.
- updated: 2026-10-31

### MPC-040 Mute
- status: open
- applies: firmware 3.10.0.49
- evidence: S-006, M02: оба поля, на экране две M; Rataklang: `Samples` и `Drum SC Input` только `program.mixable.mute`
- fact: Два независимых флага: `track.mute` и `program.mixable.mute`. Корневой `trackMutePerSequence` true во всех проектах. Какой флаг какая M, не установлено.
- not: Поле `muted` события не выключает клип.
- updated: 2026-10-31

### MPC-041 Маршрут аудио
- status: hypothesis
- applies: firmware 3.10.0.49
- evidence: схема Rataklang: все Out, Submix, Return и большинство треков 2, `Hands` и `Minilogue` 1; S-006, G01 ставил 2, AUDIO OUT остался OUT 1/2
- fact: `program.mixable.audioRoute`: `destination` 2 это основной выход, `audioRouteSubIndex` номер пары выходов (`Return SC` 3). `destination` 1 это, вероятно, сабмикс, а `audioRouteSubIndex` его номер с нуля. `channelBitmap.data` 3 или 2, смысл неизвестен. У пэдов `instruments[].mixable.audioRoute.destination` 0, вероятно, «как у программы».
- not: Запись S-006 «2 означает сабмикс» неверна: G01 оставил выход основным.
- updated: 2026-10-31

### MPC-042 MIDI-выход
- status: single-sample
- applies: firmware 3.10.0.49
- evidence: S-004, один проект; S-005, T08
- fact: `track.midiOutputRoute.outputPort.deviceName, outputChannel`, в примере это имя устройства.
- updated: 2026-10-30

### MPC-043 Выход MIDI не задан
- status: confirmed
- applies: firmware 3.10.0.49, Live 2
- evidence: S-006, M01, F01
- fact: `deviceName` `<none>` у `midiOutputRoute.outputPort` и `midiInputRoute.inputPort` открывается без ошибок, порт выбирается на Live 2.
- updated: 2026-10-30

### MPC-044 Порт A
- status: open
- applies: firmware 3.10.0.49
- evidence: S-005, S-006, отложено
- fact: Как в файле записан порт A, неизвестно.
- updated: 2026-10-30

### MPC-032 Объект track
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 962 треков, [schema.tsv](schema.tsv)
- fact: Запись `data.tracks[]`, версия 6.
- updated: 2026-10-31

| Поле | Тип | Значения | Смысл | Статус |
|---|---|---|---|---|
| `name` | str | | Имя, ключ клипов | confirmed |
| `mute` | bool | | См. MPC-040 | open |
| `volume`, `volumeKnown` | float, bool | 0.69–1.0 | Неизвестно, отличие от `mixable.volume` | unknown |
| `pan`, `panKnown` | float, bool | 0.5 | Панорама, центр 0.5 | hypothesis |
| `colour` | int | 15 значений | Цвет RGB | hypothesis |
| `program` | object | | MPC-075 | confirmed |
| `recordArm` | bool | | Меняется при сохранении | single-sample |
| `length`, `lengthFollowsSequenceLength` | int, bool | 0, true | Неизвестно | unknown |
| `midiInputRoute`, `midiOutputRoute` | object | | MPC-042 | single-sample |
| `arrangementClipMap`, `sharedClipMap` | list | | Неизвестно | unknown |
| `cvPort`, `gatePort`, `muteGroup`, `transposition`, `velocityScale`, `skipFromRowLaunch`, `padsFollowTrackColour`, `midiMonitorable`, `midiBankAndProgramNumber`, `midiEventsFilter` | | постоянные в образцах | Неизвестно | unknown |

### MPC-033 Объект clip
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 1206 клипов
- fact: `sequences[].value.trackClipMaps[][]`: `key` имя трека, `value` клип версии 3.
- updated: 2026-10-31

| Поле | Значения | Смысл | Статус |
|---|---|---|---|
| `name` | | Имя клипа | confirmed |
| `startPulses`, `endPulses` | 0; 15360, 30720 | Границы в тиках | confirmed |
| `loop`, `loopStartPulses`, `loopEndPulses` | true; 0; 15360 | Цикл | hypothesis |
| `eventList.events` | | MPC-034 | confirmed |
| `timeSignatureList` | | См. MPC-030 | open |
| `launch`, `launchQuantisation`, `legato`, `colour`, `perClipParameterValues` | постоянные | Неизвестно | unknown |

### MPC-034 Событие eventList
- status: confirmed
- applies: firmware 3.10.0.49
- evidence: схема 4650 событий, версия 2
- fact: Общие поля `time`, `type`, `channel`, `muted`, `selected`, `invented`. `type` 3 нота, 1 автоматизация.
- updated: 2026-10-31

| Поле `note` | Значения | Смысл | Статус |
|---|---|---|---|
| `note` | 0–127 | Высота | confirmed |
| `velocity` | 0.083–1.0 | Скорость нажатия, шкала 0–1 | confirmed |
| `length` | 44–15360 | Длина в тиках | confirmed |
| `probability` | 100 | Вероятность, % | hypothesis |
| `ratchet` | 1 | Рэтчет | hypothesis |
| `articulation` | 197 | Неизвестно | unknown |
| `modifierValue0–15`, `modifierActiveState0–15`, `selectedModifierType` | постоянные | Модификаторы ноты | hypothesis |
