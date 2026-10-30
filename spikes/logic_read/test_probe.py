"""Длина MIDI-региона на синтетической записи: поля сдвигаются вслед за именем."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe  # noqa: E402


def payload(name: bytes, length: int) -> bytes:
    head = bytes(0x10) + struct.pack("<H", len(name)) + name
    head += bytes(len(head) % 2)
    return head + bytes(0x3C) + struct.pack("<I", length) + bytes(8)


def test_length_with_even_and_odd_names() -> None:
    for name in (b"RGN_mute", b"RGN_sub", b"RGN_trans", b"A"):
        assert probe.midi_length(payload(name, 7680)) == 7680
