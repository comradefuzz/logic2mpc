---
id: MPC-R-004
status: applied
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: test-projects/reference/Empty.xpj, пустой проект с Live 2: 29 треков (`Drum 001` тип 0 и 28 служебных), `sequences` и `samples` пусты, `currentTrackIndex` 0, у `Drum 001` `recordArm` true; по словам пользователя служебные треки видны в интерфейсе как отдельные и удалить их на Live 2 нельзя
found-in: S-015
created: 2026-11-02
resolved: 2026-11-06
comment: Принят пользователем; номер MPC-110.
---

Предлагается записать как `single-sample`: пустой проект Live 2 не содержит ни одной секвенции, клипы живут только в `sequences[]`, поэтому у проекта без секвенций нет и клипов. Служебные треки Out, Submix, Return Live 2 не позволяет удалить, значит в любом сохранённом им проекте они есть. Нужны ли они в файле для открытия на Live 2, образец не показывает: это проверяют кейсы `Z01`–`Z03` спайка 9.
