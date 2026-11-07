"""Выбор уровня контроля (`scripts/gate.py`)."""
from __future__ import annotations

import gate


def test_code_and_tests_need_the_smoke_run() -> None:
    assert gate.touches_code(["logic2mpc/adapters/xpj.py"])
    assert gate.touches_code(["tests/test_export.py", "docs/analysis.md"])
    assert gate.touches_code(["logic2mpc/spec/pad.json"])
    assert gate.touches_code(["pytest.ini"])


def test_docs_and_stories_do_not_need_the_smoke_run() -> None:
    assert not gate.touches_code(["stories/S-024-variants-mute-group.md", "docs/glossary.md", "CLAUDE.md", ".claude/skills/accept/SKILL.md"])
    assert not gate.touches_code([])
