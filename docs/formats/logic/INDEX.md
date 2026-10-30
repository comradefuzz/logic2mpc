# Logic: спецификация

Формат проекта Logic Pro по разбору 21 `ProjectData` из `test-projects/`: Logic 10.8.1 (`0x09CB`), MONTERO 10.7.0 (`0x09C4`). Logic 11 и 12 не проверялись. Правила ведения: [README](../README.md).

Статус поля: `confirmed` проверено, `single-sample` один пример или нет эталона, `hypothesis` вывод, `unknown` поле есть, смысл неизвестен.

| Уровень | Файл | Структуры |
|---|---|---|
| Пакет и файл | [container.md](container.md) | `.logicx`, плисты, заголовок файла, заголовок записи, каталог 27 тегов |
| Дорожки | [tracks.md](tracks.md) | Trak, Envi, стеки, альтернативы |
| Регионы и аудио | [regions.md](regions.md) | Размещение, AuFl, AuRg, Mute, Loop, алиас |
| События | [notes-events.md](notes-events.md) | MSeq, роли, нота, темп, размер, маркер |
| Экспорты | [exports.md](exports.md) | MIDI, FCP XML, AAF, All Tracks |
| Версии | [versions.md](versions.md) | |
| Перепись | [records.txt](records.txt), [layouts.txt](layouts.txt) | Все теги, роли, размеры, побайтовая разметка |
| Реквесты | [requests/](requests/) | LOGIC-R-NNN |

Главные пробелы: 16 тегов без смысла, поля `unknown` в заголовке и Trak, Mute дорожки, смещение региона в файле, Track Alternatives.
