---
id: MPC-R-001
status: applied
kind: add
targets:
proposed-status: hypothesis
applies: firmware 3.10.0.49, Live 2
evidence: S-010, поля записаны в сборке Elated, на Live 2 пока не открывалось; в образцах `lengthBars` 4 и 8, `loopEndBar` только 4, `loopEndPulses` только 15360, длина ноты 44–15360
found-in: S-010
created: 2026-11-01
resolved: 2026-11-02
---

Длина секвенции задаётся полями `lengthBars`, `lengthPulses`, `loopEndBar`, `loopEndPulses` секвенции и `endPulses`, `loopEndPulses` каждого клипа. Сборка S-010 пишет их согласованно, конец цикла равен длине: 8 и 16 тактов, 61440 тиков. Запись новой длины ни один спайк не проверял, значения 16 и 61440 и длина ноты до 61440 тиков вне образцов. Десять секвенций продолжают проверенный случай с двумя. Порядок: ключи по убыванию, как в `Rataklang - Brassic`.

Предлагается записать эти поля как `hypothesis` и поднять статус после открытия проекта Elated на Live 2.
