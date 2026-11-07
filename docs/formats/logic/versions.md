# Logic: версии

### LOGIC-100 Проверенные версии
- status: single-sample
- applies: Logic 10.7.0, 10.8.1
- evidence: S-001, Spike Control, Pyro (135 дорожек), Elated (66), MONTERO (139)
- fact: Версия файла `cb09` у Logic 10.8.1, `c409` у Logic 10.7.0.
- updated: 2026-10-30

### LOGIC-101 Logic 11 и 12
- status: single-sample
- applies: Logic 12.3.1 (6682); Logic 11 не проверялась
- evidence: S-001, Logic 11 на машине нет; S-027, LOGIC-R-010: Spike Control, пересохранённый в Logic 12.3.1, `ProjectData` версии 0x09D1
- fact: Logic 12.3.1 проверена на одном проекте из 7 дорожек: контейнер и теги те же, темп, размер, маркеры, дорожки, регионы и ноты читаются кодом 10.8.1 с теми же результатами. Версия файла 0x09D1, см. LOGIC-007, LOGIC-103. Не проверялись большие проекты, Drummer и Session Players в действии, Track Alternatives. Logic 11 не проверялась, перед поддержкой пересобирается контрольный проект. Адаптер Logic 12: `logic2mpc/adapters/logic12.py`.
- updated: 2026-11-08

### LOGIC-102 Запасной путь при смене формата
- status: hypothesis
- applies: любая версия
- evidence: S-002, имена экспорта сопоставлены на контрольном проекте
- fact: Если чтение `ProjectData` сломается, структуру можно брать из имён файлов экспорта.
- updated: 2026-10-30
