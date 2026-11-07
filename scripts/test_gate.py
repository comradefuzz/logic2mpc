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


def test_fingerprint_changes_with_code_and_ignores_docs_and_story_tests() -> None:
    files = {"logic2mpc/a.py": b"1", "tests/t.py": b"2", "docs/x.md": b"3", "story_tests/S-1/t.py": b"4", "stories/S-1.md": b"5"}
    base = gate.fingerprint(list(files), files.__getitem__)
    assert gate.fingerprint(list(files), {**files, "docs/x.md": b"changed", "story_tests/S-1/t.py": b"x", "stories/S-1.md": b"y"}.__getitem__) == base
    assert gate.fingerprint(list(files), {**files, "logic2mpc/a.py": b"changed"}.__getitem__) != base
    assert gate.fingerprint(list(files), {**files, "tests/t.py": b"changed"}.__getitem__) != base


def test_fingerprint_depends_on_the_set_of_files() -> None:
    files = {"logic2mpc/a.py": b"1", "logic2mpc/b.py": b"2"}
    assert gate.fingerprint(["logic2mpc/a.py"], files.__getitem__) != gate.fingerprint(list(files), files.__getitem__)


def test_areas_follow_the_changed_paths() -> None:
    assert gate.areas_for(["logic2mpc/adapters/xpj.py"]) == {"build"}
    assert gate.areas_for(["logic2mpc/spec/pad.json", "tests/test_export.py"]) == {"build"}
    assert gate.areas_for(["logic2mpc/adapters/web.py"]) == {"web"}
    assert gate.areas_for(["logic2mpc/core/analysis.py", "tests/test_edit.py"]) == {"core"}
    assert gate.areas_for(["scripts/gate.py"]) == {"tools"}


def test_unknown_code_touches_every_area_and_docs_none() -> None:
    assert gate.areas_for(["logic2mpc/app.py"]) == set(gate.ALL_AREAS)
    assert gate.areas_for(["docs/analysis.md", "stories/S-001.md"]) == set()
