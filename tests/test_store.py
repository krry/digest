from __future__ import annotations

import json
import pathlib
import pytest

from digest.store import DigestStore, type_for_depth


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


def test_rename_node_updates_title(populated):
    store, goal, idea, step = populated
    updated = store.rename_node(goal["id"], "Renamed Goal")
    assert updated is not None
    assert updated["title"] == "Renamed Goal"
    assert store.get_node(goal["id"])["title"] == "Renamed Goal"


def test_rename_node_returns_none_for_missing(store):
    assert store.rename_node("nonexistent", "title") is None


def test_set_node_status_completes(populated):
    store, goal, idea, step = populated
    updated = store.set_node_status(goal["id"], "completed")
    assert updated["status"] == "completed"
    assert updated["completedAt"] is not None
    assert store.get_node(goal["id"])["status"] == "completed"


def test_set_node_status_active_clears_completed_at(populated):
    store, goal, idea, step = populated
    store.set_node_status(goal["id"], "completed")
    updated = store.set_node_status(goal["id"], "active")
    assert updated["completedAt"] is None


def test_set_node_status_returns_none_for_missing(store):
    assert store.set_node_status("nonexistent", "completed") is None


def test_add_node_appends_to_siblings(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    assert idea2["parentId"] == goal["id"]
    assert idea2["type"] == "idea"
    ids = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]]
    assert ids == [idea["id"], idea2["id"]]


def test_add_node_idempotent_with_same_id(populated):
    store, goal, idea, step = populated
    result = store.add_node("idea", goal["id"], "Idea B", node_id=idea["id"])
    assert result["id"] == idea["id"]
    count = len([n for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]])
    assert count == 1


def test_json_mirror_reflects_rename(populated):
    store, goal, idea, step = populated
    store.rename_node(goal["id"], "Mirror Test")
    goals = json.loads(store.goals_path.read_text())
    titles = [n["title"] for n in goals["nodes"]]
    assert "Mirror Test" in titles


def test_set_importance(populated):
    store, goal, idea, step = populated
    result = store.set_importance(goal["id"], 3)
    assert result["importance"] == 3
    assert store.get_node(goal["id"])["importance"] == 3


def test_set_importance_clear(populated):
    store, goal, idea, step = populated
    store.set_importance(goal["id"], 3)
    result = store.set_importance(goal["id"], None)
    assert result["importance"] is None


def test_set_importance_returns_none_for_missing(store):
    assert store.set_importance("nonexistent", 3) is None


def test_set_due_date(populated):
    store, goal, idea, step = populated
    result = store.set_due_date(goal["id"], "2026-12")
    assert result["dueDate"] == "2026-12"
    assert store.get_node(goal["id"])["dueDate"] == "2026-12"


def test_set_due_date_clear(populated):
    store, goal, idea, step = populated
    store.set_due_date(goal["id"], "2026-12")
    result = store.set_due_date(goal["id"], None)
    assert result["dueDate"] is None


def test_set_tags(populated):
    store, goal, idea, step = populated
    result = store.set_tags(goal["id"], ["focus", "health"])
    assert result["tags"] == ["focus", "health"]
    assert store.get_node(goal["id"])["tags"] == ["focus", "health"]


def test_set_tags_empty(populated):
    store, goal, idea, step = populated
    store.set_tags(goal["id"], ["focus"])
    result = store.set_tags(goal["id"], [])
    assert result["tags"] == []


def test_move_down_changes_order(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    store.move_down(idea["id"])
    children = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]]
    assert children == [idea2["id"], idea["id"]]


def test_move_up_changes_order(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    store.move_up(idea2["id"])
    children = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]]
    assert children == [idea2["id"], idea["id"]]


def test_move_up_noop_at_top(populated):
    store, goal, idea, step = populated
    store.add_node("idea", goal["id"], "Idea B2")
    store.move_up(idea["id"])
    children = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]]
    assert children[0] == idea["id"]


def test_move_down_noop_at_bottom(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    store.move_down(idea2["id"])
    children = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] == goal["id"]]
    assert children[-1] == idea2["id"]


def test_indent_reparents_to_previous_sibling(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    store.indent(idea2["id"])
    result = store.get_node(idea2["id"])
    assert result["parentId"] == idea["id"]


def test_indent_adjusts_type(populated):
    store, goal, idea, step = populated
    idea2 = store.add_node("idea", goal["id"], "Idea B2")
    store.indent(idea2["id"])
    result = store.get_node(idea2["id"])
    assert result["type"] == "step"


def test_indent_fails_when_no_previous_sibling(populated):
    store, goal, idea, step = populated
    with pytest.raises(ValueError, match="no previous sibling"):
        store.indent(idea["id"])


def test_unindent_reparents_to_grandparent(populated):
    store, goal, idea, step = populated
    store.unindent(idea["id"])
    result = store.get_node(idea["id"])
    assert result["parentId"] is None


def test_unindent_adjusts_type(populated):
    store, goal, idea, step = populated
    store.unindent(idea["id"])
    result = store.get_node(idea["id"])
    assert result["type"] == "goal"


def test_unindent_inserts_after_former_parent(populated):
    store, goal, idea, step = populated
    store.unindent(idea["id"])
    roots = [n["id"] for n in store.load_goals_data()["nodes"] if n["parentId"] is None]
    assert roots.index(goal["id"]) < roots.index(idea["id"])


def test_unindent_fails_at_root(populated):
    store, goal, idea, step = populated
    with pytest.raises(ValueError, match="already at root"):
        store.unindent(goal["id"])


def test_type_for_depth():
    assert type_for_depth(0) == "goal"
    assert type_for_depth(1) == "idea"
    assert type_for_depth(2) == "step"
    assert type_for_depth(3) == "task"
    assert type_for_depth(4) == "free"
    assert type_for_depth(10) == "free"
