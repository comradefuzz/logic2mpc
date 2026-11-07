"""Запись контейнера проекта MPC (`logic2mpc/adapters/mpcfile.py`)."""
from __future__ import annotations

import json

from logic2mpc.adapters.mpcfile import Number, dump


def test_dump_scalars_match_json() -> None:
    for value in ("текст", 'кавычка " и \\', "\n\t", True, False, None, 0, -7, 2**40, 1.5):
        assert dump(value) == json.dumps(value, ensure_ascii=False)


def test_dump_keeps_number_literal_and_layout() -> None:
    node = {"a": Number("1.0"), "b": [1, {"c": []}], "d": {}}
    assert dump(node) == '{\n"a": 1.0,\n"b": [\n1,\n{\n"c": []\n}\n],\n"d": {}\n}'


def test_dump_bool_is_not_written_as_a_number() -> None:
    assert dump([True, 1]) == "[\ntrue,\n1\n]"
