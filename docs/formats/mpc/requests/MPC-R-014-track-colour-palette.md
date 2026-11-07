---
id: MPC-R-014
status: open
kind: add
targets:
proposed-status: single-sample
applies: firmware 3.10.0.49, Live 2
evidence: S-025, test-projects/reference/Example Colours.xpj (сохранён Live 2, 64 драм-трека созданы подряд, цвета выставились автоматически): `tracks[].colour` у Drum 001–021 принимает 21 значение, Drum 022–042 и Drum 043–063 повторяют их в том же порядке, Drum 064 снова первое. Служебные треки: Submix 0xFF6D17, Return 0xECEC24, Out 0xA2A9AD у всех одинаково. `padsFollowTrackColour` false у всех 92 треков
found-in: S-025
created: 2026-11-07
---

Предлагается записать как `single-sample`: Live 2 назначает новому драм-треку цвет (`tracks[].colour`, целое RGB 0xRRGGBB) по кругу из 21 значения, в порядке 0x55FF00, 0x00FF80, 0x00AAFF, 0x5200FF, 0xFF00FF, 0xFF4400, 0xE6FF00, 0x11FF00, 0x00FFC4, 0x0066FF, 0x6F00FF, 0xFF00BB, 0xFF8800, 0xA2FF00, 0x00FF33, 0x00F7FF, 0x0022FF, 0xB200FF, 0xFF0077, 0xFF0000, 0xFFD500. Первый трек нового проекта получает 0x55FF00. Служебные треки красятся фиксированно: Submix 0xFF6D17, Return 0xECEC24, Out 0xA2A9AD. В этом порядке нет четырёх цветов из палитры пэдов (MPC-R-015): 0xFF6D17, 0xECEC24, 0xA2A9AD (цвета служебных треков) и 0x29B574. Порядок автоназначения образец показал на одном проекте.
