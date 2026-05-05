from __future__ import annotations

import json
import pathlib
import pytest

from digest.store import DigestStore


@pytest.fixture
def store(tmp_path: pathlib.Path) -> DigestStore:
    s = DigestStore(
        db_path=tmp_path / "test.db",
        goals_path=tmp_path / "goals.json",
        values_path=tmp_path / "values.json",
        checkins_path=tmp_path / "checkins.json",
    )
    s.ensure_ready()
    return s


@pytest.fixture
def populated(store: DigestStore) -> tuple[DigestStore, dict, dict, dict]:
    """Returns (store, goal, idea, step) — a three-level tree."""
    goal = store.add_node("goal", None, "Goal A")
    idea = store.add_node("idea", goal["id"], "Idea B")
    step = store.add_node("step", idea["id"], "Step C")
    return store, goal, idea, step
