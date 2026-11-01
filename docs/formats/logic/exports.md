# Logic: экспорты

### LOGIC-080 MIDI-файл
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, S-003, контрольный проект
- fact: Формат 1, 480 PPQ, дорожка с темпом, размером и маркерами плюс дорожки с нотами. Регион в `FF 03`, дорожка в `FF 04`, позиции абсолютные от начала проекта.
- updated: 2026-10-30

### LOGIC-081 MIDI: регионы и Loop
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-003, копия 4
- fact: Каждый регион и каждый проход Loop это отдельная MIDI-дорожка. Аудиорегионов в файле нет, выключенные регионы не попадают.
- updated: 2026-10-30

### LOGIC-082 Final Cut Pro XML
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-001, контрольный проект
- fact: Даёт имена дорожек и стеков, отдельные клипы без вложенности и файлы `CTRL_*_1.aif` на дорожку и стек от начала проекта. Темпа, нот и маркеров нет.
- updated: 2026-10-30

### LOGIC-083 AAF
- status: single-sample
- applies: Logic 10.8.1
- evidence: S-001, в файле не нашлось строк с именами, разборщиком не открывался
- fact: Apple Loops в AAF не экспортируются: Logic пропустил два таких файла.
- updated: 2026-10-30

### LOGIC-084 Export All Tracks: диалог
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, снимок диалога
- fact: Поля `Range`, `Save Format`, `Bit Depth`, `Multi-Output Software Instruments`, `Bypass Effect Plug-ins`, `Include Audio Tail`, `Include Volume/Pan Automation`, `Include Tempo Information`, `Normalize`, `Add resulting files to Project Browser`. `Range`: `Trim Silence at File End`, `Export Cycle Range Only`, `Extend File Length to Project End`.
- updated: 2026-10-30

### LOGIC-085 Export All Tracks: шаблон имён
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, 7 и 9 дорожек
- fact: `Track Number`, `_`, `Track Name` дают `NN_Имя.wav`. `Track Number` равен индексу строки дорожки с нуля плюс один, заголовки стеков считаются.
- updated: 2026-10-30

### LOGIC-086 Export All Tracks: какие строки дают файл
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, контрольный проект и копия 3
- fact: Дорожка с регионами: файл. Дорожка с Mute: файл со звуком. Summing-стек: файл-смесь без выключенных дорожек. Folder-стек и пустая дорожка: файла нет, номер пропущен. Stereo Out: файла нет.
- updated: 2026-10-30

### LOGIC-087 Export All Tracks: начало файла
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, старт совпал до тысячной секунды, `CTRL_sub` позже на шестнадцатую: первая нота
- fact: При `Trim Silence at File End` файлы начинаются с начала проекта, а длина у них разная.
- updated: 2026-10-30

### LOGIC-088 Export All Tracks: служебные чанки
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, два экспорта
- fact: При одинаковом звуке файлы различаются чанками `bext`, `ResU`, `JUNK`. Сравнивать и считать хэши надо по чанку `data`.
- updated: 2026-10-30

### LOGIC-089 Скриптовый интерфейс
- status: confirmed
- applies: Logic 10.8.1
- evidence: S-002, `LogicSuite.sdef`
- fact: В словаре AppleScript одна команда `renderPreview`, команды экспорта нет. Управление интерфейсом требует Accessibility, не проверялось.
- updated: 2026-10-30

### LOGIC-090 Настройки экспорта и звук
- status: open
- applies: Logic 10.8.1
- evidence: S-002, варианты не сравнивались, повторного экспорта не было; LOGIC-R-004, Elated 1
- fact: Влияние эффектов, фейдеров, хвоста и других `Range` не проверялось. Причина сдвига `CTRL_kick` на 3 мс не выяснена. Track Alternatives и take folders в экспорте не проверялись. Mute региона убирает его из экспорта.
- updated: 2026-10-31
