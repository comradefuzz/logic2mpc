"""S-027: Logic 12 (0x09D1) против Logic 10.8.1 (0x09CB) на Spike Control. Тесты спайка, в общий набор не входят."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import logic12 as g  # noqa: E402

L = g.L


def test_versions_of_alternatives():
    assert g.version(g.NEW_ALT) == g.VERSION_NEW
    assert g.version(g.NEW_OLD_ALT) == g.VERSION_OLD  # остаток от 10.8.1 в пакете Logic 12
    assert g.version(g.OLD_ALT) == g.VERSION_OLD


def test_product_adapter_refuses_new_version():
    """Решение пользователя: адаптер 10.8.1 не меняется, 0x09D1 для него неизвестна."""
    with pytest.raises(ValueError, match="неизвестная версия"):
        L.walk((g.NEW_ALT / "ProjectData").read_bytes())
    assert g.VERSION_NEW not in L.VERSIONS


def test_container_is_same_shape():
    new = (g.NEW_ALT / "ProjectData").read_bytes()
    assert L.u32(new, 0x10) == len(new) - 24
    records = g.load(g.NEW_ALT)
    assert len(records) == 612
    assert set(r.tag for r in records) == set(r.tag for r in g.load(g.OLD_ALT)), "новых тегов нет"


def test_record_counts_changed_as_documented():
    new, old = g.profile(g.load(g.NEW_ALT)), g.profile(g.load(g.OLD_ALT))
    assert sum(new.values()) == 612 and sum(old.values()) == 521
    assert new[("karT", 23)] == 49 and old[("karT", 23)] == 47
    assert new[("MneG", 30)] == 6 and old[("MneG", 30)] == 5


def test_record_header_revision_fields():
    new, old = g.load(g.NEW_ALT), g.load(g.OLD_ALT)
    assert {L.u16(r.raw, 0x1A) for r in new} == {2}
    assert {L.u16(r.raw, 0x1A) for r in old} == {1}
    song_new = next(r for r in new if r.tag == "gnoS")
    song_old = next(r for r in old if r.tag == "gnoS")
    assert L.u16(song_new.raw, 36 + 4) == g.VERSION_NEW and L.u16(song_old.raw, 36 + 4) == g.VERSION_OLD


def test_trak_payload_has_one_extra_byte():
    new = {len(r.raw) for r in g.load(g.NEW_ALT) if r.tag == "karT"}
    old = {len(r.raw) for r in g.load(g.OLD_ALT) if r.tag == "karT"}
    assert new == {36, 94} and old == {36, 93}


def test_same_reading_on_both_versions():
    assert g.read_all(g.load(g.NEW_ALT)) == g.read_all(g.load(g.OLD_ALT))


def test_reading_content_is_the_control_project():
    got = g.read_all(g.load(g.NEW_ALT))
    assert [t for _, t in got["tempo"]] == [100.0, 140.0]
    assert [(n, d) for _, n, d in got["meter"]] == [(4, 4), (3, 4), (4, 4)]
    assert [m for _, m in got["markers"]] == ["MRK_A", "MRK_B", "MRK_C"]
    assert len(got["rows"]) == 8 and got["rows"][-1][1] == "Stereo Out"
    assert sorted(got["audio"]) == [3, 6] and sorted(got["midi"]) == [1, 5]


def test_untouched_alternative_equal_to_original():
    new = (g.NEW_OLD_ALT / "ProjectData").read_bytes()
    old = (g.OLD_ALT_1 / "ProjectData").read_bytes()
    assert new == old


def test_midi_end_of_track_at_bar_in_logic12():
    """В 10.8.1 End of Track стоит на последней ноте, в Logic 12 позже и на границе такта (гипотеза: конец региона)."""
    bar = 480 * 4
    new = [t for t in g.midi_tracks(g.NEW_MID) if t["name"].startswith("RGN_")]
    old = [t for t in g.midi_tracks(g.OLD_MID) if t["name"].startswith("RGN_")]
    assert [t["name"] for t in new] == [t["name"] for t in old] == ["RGN_kick", "RGN_sub"]
    assert all(t["eot"] == t["last_off"] for t in old)
    assert all(t["eot"] > t["last_off"] and t["eot"] % bar == 0 for t in new)
    assert [t["last_off"] for t in new] == [t["last_off"] for t in old]


def test_all_tracks_lengths_equal_in_frames():
    import wave

    new = {p.stem: p for p in (g.ROOT / "test-projects/reference/L12/all-tracks-l12").glob("*.wav")}
    old = {p.stem[3:]: p for p in (g.ROOT / "test-projects/exports/all-tracks").glob("*.wav")}
    assert sorted(new) == sorted(old) and len(new) == 7
    for name in new:
        with wave.open(str(new[name])) as a, wave.open(str(old[name])) as b:
            assert a.getnframes() == b.getnframes() and a.getframerate() == b.getframerate()


def test_record_revision_byte_by_tag():
    new, old = g.load(g.NEW_ALT), g.load(g.OLD_ALT)
    pick = lambda recs, tag: {r.raw[4] for r in recs if r.tag == tag}  # noqa: E731
    assert (pick(new, "karT"), pick(old, "karT")) == ({6}, {5})
    assert (pick(new, "qeSM"), pick(old, "qeSM")) == ({5}, {3})
    assert (pick(new, "OCuA"), pick(old, "OCuA")) == ({7}, {5})
    assert (pick(new, "gnoS"), pick(old, "gnoS")) == ({8}, {3})


def test_new_records_and_sizes():
    new, old = g.profile(g.load(g.NEW_ALT)), g.profile(g.load(g.OLD_ALT))
    assert (new[("OCuA", 14)], old[("OCuA", 14)]) == (373, 289)
    assert (new[("UCuA", 14)], old[("UCuA", 14)]) == (9, 7)
    recs = g.load(g.NEW_ALT)
    song = next(r for r in recs if r.tag == "gnoS")
    assert len(song.payload) == 23038 and len(next(r for r in g.load(g.OLD_ALT) if r.tag == "gnoS").payload) == 3716
    gen = next(r for r in recs if r.tag == "MneG" and r.idx == 0x140000)
    assert b"genInstDrummerBaseModel.state" in gen.raw
    assert any(r.tag == "qeSM" and r.role == 0x17 and r.idx == 0x3C0000 for r in recs)
    assert any(r.tag == "qSvE" and r.role == 0x17 and r.idx == 0x3C0000 for r in recs)


def test_package_plists():
    import plistlib

    pkg = g.NEW_ALT.parents[1]
    info = plistlib.loads((pkg / "Resources/ProjectInformation.plist").read_bytes())
    old = plistlib.loads((g.OLD_ALT.parents[1] / "Resources/ProjectInformation.plist").read_bytes())
    assert info["BundleVersion"] == old["BundleVersion"] == 2
    assert info["LastSavedFrom"].startswith("Logic Pro Creator Studio 12.3.1") and info["ActiveVariant"] == 0
    meta = plistlib.loads((g.NEW_ALT / "MetaData.plist").read_bytes())
    meta_old = plistlib.loads((g.OLD_ALT / "MetaData.plist").read_bytes())
    assert set(meta) == set(meta_old)
    assert meta["BeatsPerMinute"] == 100 and meta["NumberOfTracks"] == 7 and meta["SampleRate"] == 48000
    assert all(p.startswith("${CONTENT_iOS:Logic Pro Library.bundle}") for p in meta["SamplerInstrumentsFiles"])
    assert not any(p.startswith("${CONTENT_iOS") for p in meta_old["SamplerInstrumentsFiles"])


def test_fcpxml_version_and_midi_eot_values():
    import re

    assert 'fcpxml version="1.8"' in (g.NEW_MID.parent / "Spike Control copy.fcpxml").read_text()
    new = {t["name"]: t["eot"] for t in g.midi_tracks(g.NEW_MID)}
    assert new["RGN_kick"] == 7680 and new["RGN_sub"] == 15360
    assert re.fullmatch(r"RGN_\w+", "RGN_kick")
