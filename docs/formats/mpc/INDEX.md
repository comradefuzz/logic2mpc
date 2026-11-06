# MPC: спецификация

Формат `.xpj` и `.xpm` по разбору 33 файлов из `test-projects/mpc`, прошивка 3.10.0.49. Правила ведения: [README](../README.md).

Статус поля: `confirmed` проверено, `single-sample` один пример, `hypothesis` вывод, `unknown` поле есть, смысл неизвестен.

| Уровень | Файл | Структуры |
|---|---|---|
| Файл | [container.md](container.md) | Gzip, заголовок, корень `data` |
| Проект | [project.md](project.md) | track, clip, событие, секвенция, маршрут, Mute |
| Программа | [programs.md](programs.md) | program, instrument, layer, кейгруппа, плагин |
| Сэмплы | [samples.md](samples.md) | sample, папка, форматы |
| Поведение Live 2 | [device.md](device.md) | Что меняется при сохранении |
| Версии | [versions.md](versions.md) | |
| Схема | [schema.tsv](schema.tsv) | Все 3122 пути: тип, частота, значения, типы программ |
| Реестр для экспорта | [export.tsv](export.tsv) | Поля, которые создаёт экспорт: класс, обязательность, значение, факт. Заполнен по раундам 1 и 2 спайка 9: `required` yes/no/unknown со ссылкой на факт |
| Реквесты | [requests/](requests/) | MPC-R-NNN |

Четвёртый столбец `schema.tsv` это типы программ, он заполнен только для `data.tracks[].program`. Пустой столбец значит, что путь вне программы проекта или относится к отдельному `.xpm`.

Быстрый поиск: кейгруппа MPC-064, маршрут MPC-041, монофония MPC-067, Mute MPC-040, размер MPC-030.
