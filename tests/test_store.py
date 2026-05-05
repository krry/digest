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


def test_get_node_returns_correct_node(populated):
    store, goal, idea, step = populated
    result = store.get_node(goal["id"])
    assert result is not None
    assert result["id"] == goal["id"]
    assert result["type"] == "goal"
    assert result["title"] == "Goal A"
    assert result["parentId"] is None


def test_get_node_returns_none_for_missing(store):
    assert store.get_node("nonexistent") is None


def test_find_active_matches_filters_by_title(populated):
    store, goal, idea, step = populated
    results = store.find_active_matches("idea")
    assert len(results) == 1
    assert results[0]["id"] == idea["id"]


def test_find_active_matches_excludes_completed(populated):
    store, goal, idea, step = populated
    store.set_node_status(idea["id"], "completed")
    results = store.find_active_matches("idea")
    assert results == []


def test_find_active_matches_case_insensitive(populated):
    store, goal, idea, step = populated
    results = store.find_active_matches("GOAL")
    assert len(results) == 1
    assert results[0]["id"] == goal["id"]
