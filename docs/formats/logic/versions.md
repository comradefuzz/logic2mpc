# Logic: версии

### LOGIC-100 Проверенные версии
- status: single-sample
- applies: Logic 10.7.0, 10.8.1
- evidence: S-001, Spike Control, Pyro (135 дорожек), Elated (66), MONTERO (139)
- fact: Версия файла `cb09` у Logic 10.8.1, `c409` у Logic 10.7.0.
- updated: 2026-10-30

### LOGIC-101 Logic 11 и 12
- status: open
- applies: Logic 11, 12
- evidence: S-001, такой версии на машине нет
- fact: Не проверялись. Перед поддержкой новой версии контрольный проект пересобирается и сверяется заново.
- updated: 2026-10-30

### LOGIC-102 Запасной путь при смене формата
- status: hypothesis
- applies: любая версия
- evidence: S-002, имена экспорта сопоставлены на контрольном проекте
- fact: Если чтение `ProjectData` сломается, структуру можно брать из имён файлов экспорта.
- updated: 2026-10-30
