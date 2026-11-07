---
id: LOGIC-R-013
status: applied
kind: add
targets:
proposed-status: single-sample
applies: Logic 12.3.1 (6682)
evidence: S-027, Spike Control copy.logicx, `Spike Control copy.mid`, `Spike Control copy.fcpxml`, `all-tracks-l12/`; story_tests/S-027/test_logic12.py
found-in: S-027
created: 2026-11-07
resolved: 2026-11-08
comment: Принято по решению пользователя без отдельной проверки (LOGIC-104)
---

Пакет: `ProjectInformation.plist` `BundleVersion` 2 (как у 10.8.1), `LastSavedFrom` «Logic Pro Creator Studio 12.3.1 (6682)». Пакет может смешивать версии: после пересохранения активна альтернатива 000 версии 0x09D1, альтернатива 001 осталась побайтово как в 10.8.1 (0x09CB). `MetaData.plist` с теми же ключами, пути `SamplerInstrumentsFiles` теперь вида `${CONTENT_iOS:Logic Pro Library.bundle}/Plug-In Settings/Sampler/…` вместо `/Library/Application Support/Logic/Sampler Instruments/…`.

MIDI-экспорт (LOGIC-080): устройство то же, формат 1, 480 PPQ. Отличие: End of Track дорожки региона стоит на границе такта позже последней ноты (kick на 7680, sub на 15360 тиках), у 10.8.1 сразу на последней ноте off. Гипотеза: конец региона, без сверки с длиной региона.

FCP XML версии 1.8 по структуре и длинам не отличается. All Tracks: те же 7 файлов и те же длины в кадрах; имя без префикса `NN_` и 16 бит вместо 24 это выбор в диалоге, а не изменение формата.
