# Контрольный проект для спайка 1

Цель: дать значения, которые заранее известны, чтобы сверить с ними `probe.py`. Около 30 минут. Все файлы кладутся в `test-projects/`. Если пункта меню нет или что-то сделано иначе, просто запиши это.

## 1. Быстрая сверка на реальных проектах

Команды показывают дерево стеков, в квадратных скобках заголовки стеков.

```bash
python3 spikes/logic_read/probe.py tree "test-projects/copies/Fuzz - Pyro.logicx"
```

```bash
python3 spikes/logic_read/probe.py tree "test-projects/copies/Fuzz - Elated.logicx"
```

- [ ] Порядок дорожек, стеки и вложенность совпали с Logic. Pyro: ___ Elated: ___
- [ ] Маркеров в Pyro и Elated действительно нет. Pyro: ___ Elated: ___

## 2. Сборка `test-projects/Spike Control.logicx`

Делай шаги по порядку. Имена ставь точно как здесь.

**Шаг 1. Проект.** Новый пустой проект, темп 100, размер 4/4.

**Шаг 2. Дорожки.** Создай четыре дорожки сверху вниз:

| № | Имя | Тип |
|---|---|---|
| 1 | `CTRL_kick` | Software Instrument |
| 2 | `CTRL_loop` | Audio |
| 3 | `CTRL_sub` | Software Instrument |
| 4 | `CTRL_free` | Audio |

**Шаг 3. Содержимое.** На каждую дорожку один регион. В Software Instrument это MIDI-регион с любыми нотами, в Audio любой аудиофайл, обрезанный до нужной длины.

| Дорожка | Имя региона | Начало, такт | Длина, тактов |
|---|---|---|---|
| `CTRL_kick` | `RGN_kick` | 3 | 2 |
| `CTRL_loop` | `RGN_loop` | 5 | 2 |
| `CTRL_sub` | `RGN_sub` | 7 | 2 |
| `CTRL_free` | `RGN_free` | 9 | 1 |

**Шаг 4. Стеки.** Строго в этом порядке, `Track > Create Track Stack`:

1. Выдели `CTRL_loop`, создай Summing Stack, назови `CTRL_inner`.
2. Выдели `CTRL_kick` и `CTRL_inner`, создай Summing Stack, назови `CTRL_drums`.
3. Выдели `CTRL_sub`, создай Folder Stack, назови `CTRL_bass`.
4. `CTRL_free` не трогай, она остаётся вне стеков.

Итог в списке дорожек:

```
CTRL_drums
  CTRL_kick
  CTRL_inner
    CTRL_loop
CTRL_bass
  CTRL_sub
CTRL_free
```

**Шаг 5. Глобальные дорожки.**

- Маркеры: `MRK_A` на такте 2, `MRK_B` на такте 6, `MRK_C` на такте 11.
- Темп: 140 с такта 5.
- Размер: 3/4 с такта 11, снова 4/4 с такта 13.

**Шаг 6. Альтернативы.**

1. Сохрани как `test-projects/Spike Control.logicx`, формат `Package`.
2. Сделай новую альтернативу, в ней переименуй `CTRL_free` в `CTRL_free_alt`.
3. Вернись в первую альтернативу, чтобы активной была она, и сохрани.

## 3. Копии для сравнения

Команда `Save A Copy As…` после каждого шага, каждая правка от предыдущего состояния.

- [ ] `Spike Control 1 region.logicx`: `RGN_free` сдвинут с такта 9 на такт 10.
- [ ] `Spike Control 2 length.logicx`: `RGN_free` укорочен вдвое.
- [ ] `Spike Control 3 folder.logicx`: `CTRL_bass` из folder переделан в summing.

## 4. Экспорт

Из исходного проекта в `test-projects/exports/`:

- [ ] MIDI (выделить все регионы, `File > Export > Selection as MIDI File`).
- [ ] AAF (`File > Export > Project as AAF`).
- [ ] Final Cut Pro XML (`File > Export > Project to Final Cut Pro/XML`).

Названия пунктов не проверены на твоей версии.

## 5. Готово

- [ ] Напиши в сессию, что `test-projects/Spike Control.logicx` готов, и приложи итоги раздела 1.
