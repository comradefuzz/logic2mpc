---
id: MPC-R-003
status: applied
kind: add
targets:
proposed-status: confirmed
applies: firmware 3.10.0.49, Live 2
evidence: Elated.xpj, собранный экспортом: `recordArm` true у всех 8 музыкальных треков, на Live 2 пэд запускает сэмпл на всех дорожках сразу, плейбек независим. В сохранённых на Live 2 `Rataklang - Brassic.xpj` и `T10 resaved.xpj` true только у трека `currentTrackIndex`. Сборка с одним `recordArm` на Live 2 ещё не проверялась
found-in: разбор пэдов Elated
created: 2026-11-02
resolved: 2026-11-06
comment: Принят как факт по решению пользователя; номер MPC-111.
---

Предлагается записать как `hypothesis`: `tracks[].recordArm` true значит, что игра на пэдах идёт в этот трек. Несколько таких треков слышат пэды одновременно, на воспроизведение секвенции поле не влияет. Live 2 при сохранении оставляет true только у `currentTrackIndex`. Копия трека наследует поле, поэтому сборка оставляет true только у текущего трека.
