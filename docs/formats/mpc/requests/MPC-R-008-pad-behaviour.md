---
id: MPC-R-008
status: applied
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: S-015, раунд 1, кейсы P01–P06 (`test-projects/mpc/spike9/`, основа `spike7/D01 pads16`: `triggerMode` 0, `monophonic` true, `polyphony` 1), открыты на Live 2 пользователем. P01 `triggerMode` 0→2: у всех пэдов Note On, играет по длительности нот. P02 `monophonic` false, `polyphony` 1: у всех Sample Play = One Shot, звук не прерывается до конца сэмпла. P03 `monophonic` false, `polyphony` 4: One Shot, Poly 4, полифония работает. P04 у пэдов убраны постоянные поля: сэмплы в пуле проекта загружены, назначений на пэды нет, после ручного назначения пэд триггерится, уровни в нуле, звука нет. P05 `warpEnable` true: слышны артефакты warp. P06 `whichMuteGroup` 1 у двух пэдов: Mute Group = 1, один глушит другой
found-in: S-015
created: 2026-11-06
resolved: 2026-11-06
comment: Принят по прямому наблюдению пользователя на Live 2; номер MPC-115.
---

Предлагается записать как `single-sample`: на пэде драм-программы `triggerMode` 0 это One Shot, 2 это Note On (звук держится по длительности ноты). `monophonic` false при `polyphony` 1 не обрывает звук повторным ударом, при `polyphony` 4 работает полифония до четырёх голосов. `warpEnable` true включает варп, он слышен как артефакты. `whichMuteGroup` 1 даёт Mute Group 1, пэды одной группы глушат друг друга. Постоянные поля пэда выкинуть нельзя: без них пэд не получает назначений, а после ручного назначения уровни остаются в нуле, и звука нет, то есть значения по умолчанию в Live 2 не равны значениям из образцов. Какие именно из них нужны, не выяснено.
