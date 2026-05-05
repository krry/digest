# Digest Mobile Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all six phases of the Digest mobile architecture — store refactor, missing API commands, PWA node actions, values display, and deployment scripts.

**Architecture:** DigestStore gets direct SQL methods replacing the round-trip delete/reinsert pattern. The stdlib HTTP API gets the seven missing command endpoints. The PWA gets bug fixes, full node action coverage, and the new mutation types wired through the offline queue.

**Tech Stack:** Python 3.14 / sqlite3 / stdlib http.server / vanilla JS ES modules / IndexedDB / Service Worker / pytest

---

## File Map

| File | Change |
|------|--------|
| `digest/store.py` | Refactor write methods to direct SQL; add 7 new commands; extract `_row_to_node` helper |
| `digest/api.py` | Add 7 new endpoints; fix bootstrap nodeOrder; fix asset serving |
| `web/app.js` | Fix 3 bugs; add 7 new mutation types with local apply; add card UI for new actions |
| `web/styles.css` | Add styles for detail panel, importance picker, move/indent buttons |
| `tests/__init__.py` | Empty, marks tests as a package |
| `tests/test_store.py` | pytest tests for all store methods |
| `bin/digest-serve.sh` | New: server startup script |
| `bin/digest-backup.sh` | New: SQLite backup script |
| `docs/tailscale-serve.md` | New: tailscale serve setup instructions |

---

## Task 1: Fix three bugs in app.js

**Files:**
- Modify: `web/app.js`

- [ ] **Fix XSS in renderFocusCard**

In `web/app.js`, find `renderFocusCard` (~line 152). Change the focus title line from:

    <h2 class="focus-title">${node.title}</h2>

To:

    <h2 class="focus-title">${escapeHtml(node.title)}</h2>

Also wrap `node.status` in `escapeHtml()` in the focus-meta span.

- [ ] **Fix mutation dequeue bug**

Every mutation needs an `id` at queue time. Update the three action listeners in `renderList` and the composer submit handler so every `queueMutation` call passes an object with `id: generateId()`.

Change the rename listener:
```js
  els.list.querySelectorAll("[data-rename]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-rename");
      const node = nodeById(id);
      if (!node) return;
      const title = window.prompt("Rename node", node.title)?.trim();
      if (!title) return;
      await queueMutation({ id: generateId(), type: "rename-node", nodeId: id, title });
    });
  });
```

Change the complete listener:
```js
  els.list.querySelectorAll("[data-complete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-complete");
      if (!id) return;
      await queueMutation({ id: generateId(), type: "complete-node", nodeId: id });
    });
  });
```

Change the archive listener:
```js
  els.list.querySelectorAll("[data-archive]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-archive");
      if (!id) return;
      await queueMutation({ id: generateId(), type: "archive-node", nodeId: id });
    });
  });
```

- [ ] **Fix visibleNodes index scope bug**

In `visibleNodes` (~line 90), change:
```js
    return state.nodes
      .filter((node, index) => node.type === type && node.status !== "archived")
      .map((node) => ({ ...node, sortIndex: index }));
```
To:
```js
    return state.nodes
      .filter((node) => node.type === type && node.status !== "archived")
      .map((node, index) => ({ ...node, sortIndex: index }));
```

- [ ] **Commit**
```bash
git add web/app.js
git commit -m "fix: XSS in focus card, mutation dequeue, visibleNodes index scope"
```

---

## Task 2: Set up test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_store.py`

- [ ] **Create tests package**
```bash
mkdir -p /Users/kerry/gist/tests
touch /Users/kerry/gist/tests/__init__.py
```

- [ ] **Write the test fixture in `tests/test_store.py`**

```python
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
```

- [ ] **Run fixture smoke test**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 0 tests collected, no errors.

- [ ] **Commit**
```bash
git add tests/
git commit -m "test: add store test infrastructure"
```

---

## Task 3: Extract `_row_to_node` and refactor read methods

**Files:**
- Modify: `digest/store.py`
- Modify: `tests/test_store.py`

- [ ] **Write failing tests — append to `tests/test_store.py`**

```python
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
```

- [ ] **Run to confirm failures**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 5 failures (methods still use load_goals_data).

- [ ] **Add `_row_to_node` helper to `DigestStore` in `store.py`** (place before `load_goals_data`)

```python
def _row_to_node(self, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "status": row["status"],
        "parentId": row["parent_id"],
        "importance": row["importance"],
        "dueDate": row["due_date"],
        "tags": json.loads(row["tags_json"]),
        "createdAt": row["created_at"],
        "completedAt": row["completed_at"],
    }
```

- [ ] **Replace `get_node` with direct SQL**

```python
def get_node(self, node_id: str) -> dict[str, Any] | None:
    self.ensure_ready()
    with self.connect() as conn:
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    return self._row_to_node(row) if row else None
```

- [ ] **Replace `find_active_matches` with direct SQL**

```python
def find_active_matches(self, query: str) -> list[dict[str, Any]]:
    self.ensure_ready()
    with self.connect() as conn:
        rows = conn.execute(
            "select * from nodes where status = 'active' and lower(title) like lower(?)",
            (f"%{query}%",),
        ).fetchall()
    return [self._row_to_node(row) for row in rows]
```

- [ ] **Update `_export_nodes_preorder` to use `_row_to_node`**

```python
def _export_nodes_preorder(self, conn: sqlite3.Connection, parent_id: str | None, out: list[dict[str, Any]]):
    for row in self._ordered_nodes(conn, parent_id):
        out.append(self._row_to_node(row))
        self._export_nodes_preorder(conn, row["id"], out)
```

- [ ] **Run tests**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: all 5 tests pass.

- [ ] **Commit**
```bash
git add digest/store.py tests/test_store.py
git commit -m "refactor: extract _row_to_node, direct SQL for get_node and find_active_matches"
```

---

## Task 4: Refactor write methods to direct SQL

**Files:**
- Modify: `digest/store.py`
- Modify: `tests/test_store.py`

- [ ] **Write failing tests — append to `tests/test_store.py`**

```python
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
```

- [ ] **Run to confirm failures**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 8 new failures.

- [ ] **Replace `rename_node` with direct SQL**

```python
def rename_node(self, node_id: str, title: str) -> dict[str, Any] | None:
    self.ensure_ready()
    with self.connect() as conn:
        conn.execute("update nodes set title = ? where id = ?", (title, node_id))
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    if not row:
        return None
    self.export_json_mirror()
    return self._row_to_node(row)
```

- [ ] **Replace `set_node_status` with direct SQL**

```python
def set_node_status(self, node_id: str, status: str) -> dict[str, Any] | None:
    self.ensure_ready()
    completed_at = now_utc() if status == "completed" else None
    with self.connect() as conn:
        conn.execute(
            "update nodes set status = ?, completed_at = ? where id = ?",
            (status, completed_at, node_id),
        )
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    if not row:
        return None
    self.export_json_mirror()
    return self._row_to_node(row)
```

- [ ] **Replace `add_node` with direct SQL**

```python
def add_node(
    self,
    node_type: str,
    parent_id: str | None,
    title: str,
    node_id: str | None = None,
) -> dict[str, Any]:
    self.ensure_ready()
    _id = node_id or new_id()
    with self.connect() as conn:
        existing = conn.execute("select * from nodes where id = ?", (_id,)).fetchone()
        if existing:
            return self._row_to_node(existing)
        ts = now_utc()
        conn.execute(
            """
            insert into nodes(id, type, title, status, parent_id, importance, due_date, tags_json, created_at, completed_at)
            values (?, ?, ?, 'active', ?, null, null, '[]', ?, null)
            """,
            (_id, node_type, title, parent_id, ts),
        )
        row_idx = conn.execute(
            "select coalesce(max(sort_index), -1) + 1 from node_order where parent_id is ?",
            (parent_id,),
        ).fetchone()
        next_index = row_idx[0]
        conn.execute(
            "insert into node_order(node_id, parent_id, sort_index) values (?, ?, ?)",
            (_id, parent_id, next_index),
        )
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (_id,)).fetchone()
    self.export_json_mirror()
    return self._row_to_node(row)
```

- [ ] **Fix `bootstrap_payload` double-load and populate nodeOrder**

```python
def bootstrap_payload(self) -> dict[str, Any]:
    ts = now_utc()
    goals = self.load_goals_data()
    values = self.load_values_data()
    checkins = self.load_checkins_data()
    with self.connect() as conn:
        order_rows = conn.execute(
            "select node_id, parent_id, sort_index from node_order order by parent_id, sort_index"
        ).fetchall()
    node_order = [
        {"nodeId": r["node_id"], "parentId": r["parent_id"], "sortIndex": r["sort_index"]}
        for r in order_rows
    ]
    return {
        "serverTime": ts,
        "nodes": goals["nodes"],
        "nodeOrder": node_order,
        "values": {
            "establishedAt": values["establishedAt"],
            "items": values["values"],
        },
        "checkins": checkins["checkins"],
        "syncCursor": ts,
    }
```

- [ ] **Run all tests**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: all pass.

- [ ] **Commit**
```bash
git add digest/store.py tests/test_store.py
git commit -m "refactor: direct SQL for rename, set_status, add_node; fix bootstrap double-load; populate nodeOrder"
```

---

## Task 5: Add set_importance, set_due_date, set_tags

**Files:**
- Modify: `digest/store.py`
- Modify: `tests/test_store.py`

- [ ] **Write failing tests — append to `tests/test_store.py`**

```python
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
```

- [ ] **Run to confirm failures**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 7 new failures.

- [ ] **Implement in `store.py` — add after `set_node_status`**

```python
def set_importance(self, node_id: str, importance: int | None) -> dict[str, Any] | None:
    self.ensure_ready()
    with self.connect() as conn:
        conn.execute("update nodes set importance = ? where id = ?", (importance, node_id))
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    if not row:
        return None
    self.export_json_mirror()
    return self._row_to_node(row)

def set_due_date(self, node_id: str, due_date: str | None) -> dict[str, Any] | None:
    self.ensure_ready()
    with self.connect() as conn:
        conn.execute("update nodes set due_date = ? where id = ?", (due_date, node_id))
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    if not row:
        return None
    self.export_json_mirror()
    return self._row_to_node(row)

def set_tags(self, node_id: str, tags: list[str]) -> dict[str, Any] | None:
    self.ensure_ready()
    with self.connect() as conn:
        conn.execute(
            "update nodes set tags_json = ? where id = ?",
            (json.dumps(tags), node_id),
        )
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    if not row:
        return None
    self.export_json_mirror()
    return self._row_to_node(row)
```

- [ ] **Run all tests**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: all pass.

- [ ] **Commit**
```bash
git add digest/store.py tests/test_store.py
git commit -m "feat: add set_importance, set_due_date, set_tags store methods"
```

---

## Task 6: Add move_up and move_down

**Files:**
- Modify: `digest/store.py`
- Modify: `tests/test_store.py`

- [ ] **Write failing tests — append to `tests/test_store.py`**

```python
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
```

- [ ] **Run to confirm failures**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 4 new failures.

- [ ] **Implement in `store.py` — add after `set_tags`**

```python
def move_up(self, node_id: str) -> None:
    self.ensure_ready()
    with self.connect() as conn:
        current = conn.execute(
            "select parent_id, sort_index from node_order where node_id = ?", (node_id,)
        ).fetchone()
        if not current:
            return
        prev = conn.execute(
            """
            select node_id, sort_index from node_order
            where parent_id is ? and sort_index < ?
            order by sort_index desc limit 1
            """,
            (current["parent_id"], current["sort_index"]),
        ).fetchone()
        if not prev:
            return
        conn.execute(
            "update node_order set sort_index = ? where node_id = ?",
            (prev["sort_index"], node_id),
        )
        conn.execute(
            "update node_order set sort_index = ? where node_id = ?",
            (current["sort_index"], prev["node_id"]),
        )
        conn.commit()
    self.export_json_mirror()

def move_down(self, node_id: str) -> None:
    self.ensure_ready()
    with self.connect() as conn:
        current = conn.execute(
            "select parent_id, sort_index from node_order where node_id = ?", (node_id,)
        ).fetchone()
        if not current:
            return
        nxt = conn.execute(
            """
            select node_id, sort_index from node_order
            where parent_id is ? and sort_index > ?
            order by sort_index asc limit 1
            """,
            (current["parent_id"], current["sort_index"]),
        ).fetchone()
        if not nxt:
            return
        conn.execute(
            "update node_order set sort_index = ? where node_id = ?",
            (nxt["sort_index"], node_id),
        )
        conn.execute(
            "update node_order set sort_index = ? where node_id = ?",
            (current["sort_index"], nxt["node_id"]),
        )
        conn.commit()
    self.export_json_mirror()
```

- [ ] **Run all tests**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: all pass.

- [ ] **Commit**
```bash
git add digest/store.py tests/test_store.py
git commit -m "feat: add move_up and move_down store methods"
```

---

## Task 7: Add indent and unindent

**Files:**
- Modify: `digest/store.py`
- Modify: `tests/test_store.py`

- [ ] **Add TYPE_FOR_DEPTH constant and helpers to `store.py`**

Near the top of `store.py`, after `VALID_STATUSES`, add:

```python
TYPE_FOR_DEPTH = ["goal", "idea", "step", "task"]

def type_for_depth(depth: int) -> str:
    return TYPE_FOR_DEPTH[depth] if depth < len(TYPE_FOR_DEPTH) else "free"
```

Add this private method to `DigestStore`:

```python
def _node_depth(self, conn: sqlite3.Connection, node_id: str) -> int:
    depth = 0
    current = node_id
    while True:
        row = conn.execute("select parent_id from nodes where id = ?", (current,)).fetchone()
        if not row or row["parent_id"] is None:
            break
        depth += 1
        current = row["parent_id"]
    return depth
```

- [ ] **Write failing tests — append to `tests/test_store.py`**

```python
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
```

- [ ] **Run to confirm failures**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: 8 new failures.

- [ ] **Implement indent and unindent in `store.py` — add after `move_down`**

```python
def indent(self, node_id: str) -> dict[str, Any]:
    """Make node the last child of its previous sibling."""
    self.ensure_ready()
    with self.connect() as conn:
        current_order = conn.execute(
            "select parent_id, sort_index from node_order where node_id = ?", (node_id,)
        ).fetchone()
        if not current_order:
            raise ValueError(f"Node {node_id} not found")
        prev_sibling = conn.execute(
            """
            select no.node_id from node_order no
            where no.parent_id is ? and no.sort_index < ?
            order by no.sort_index desc limit 1
            """,
            (current_order["parent_id"], current_order["sort_index"]),
        ).fetchone()
        if not prev_sibling:
            raise ValueError(f"no previous sibling for {node_id}")
        new_parent_id = prev_sibling["node_id"]
        new_depth = self._node_depth(conn, new_parent_id) + 1
        new_type = type_for_depth(new_depth)
        last_child_idx = conn.execute(
            "select coalesce(max(sort_index), -1) + 1 from node_order where parent_id = ?",
            (new_parent_id,),
        ).fetchone()[0]
        conn.execute(
            "update nodes set parent_id = ?, type = ? where id = ?",
            (new_parent_id, new_type, node_id),
        )
        conn.execute(
            "update node_order set parent_id = ?, sort_index = ? where node_id = ?",
            (new_parent_id, last_child_idx, node_id),
        )
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    self.export_json_mirror()
    return self._row_to_node(row)

def unindent(self, node_id: str) -> dict[str, Any]:
    """Make node the next sibling of its current parent."""
    self.ensure_ready()
    with self.connect() as conn:
        node_row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
        if not node_row:
            raise ValueError(f"Node {node_id} not found")
        current_parent_id = node_row["parent_id"]
        if current_parent_id is None:
            raise ValueError(f"already at root: {node_id}")
        parent_order = conn.execute(
            "select parent_id, sort_index from node_order where node_id = ?",
            (current_parent_id,),
        ).fetchone()
        new_parent_id = parent_order["parent_id"] if parent_order else None
        insert_after = parent_order["sort_index"] if parent_order else -1
        conn.execute(
            """
            update node_order set sort_index = sort_index + 1
            where parent_id is ? and sort_index > ?
            """,
            (new_parent_id, insert_after),
        )
        new_sort = insert_after + 1
        new_depth = self._node_depth(conn, new_parent_id) + 1 if new_parent_id else 0
        new_type = type_for_depth(new_depth)
        conn.execute(
            "update nodes set parent_id = ?, type = ? where id = ?",
            (new_parent_id, new_type, node_id),
        )
        conn.execute(
            "update node_order set parent_id = ?, sort_index = ? where node_id = ?",
            (new_parent_id, new_sort, node_id),
        )
        conn.commit()
        row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
    self.export_json_mirror()
    return self._row_to_node(row)
```

- [ ] **Run all tests**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m pytest tests/test_store.py -v
```
Expected: all pass.

- [ ] **Commit**
```bash
git add digest/store.py tests/test_store.py
git commit -m "feat: add indent, unindent, type_for_depth to store"
```

---

## Task 8: Fix asset serving and add new API endpoints

**Files:**
- Modify: `digest/api.py`

- [ ] **Fix asset serving — replace `_serve_web_path`**

```python
ALLOWED_EXTENSIONS = {".html", ".css", ".js", ".webmanifest", ".png", ".svg", ".ico"}

def _serve_web_path(path: str) -> pathlib.Path | None:
    name = "index.html" if path == "/" else path.lstrip("/")
    target = (WEB_ROOT / name).resolve()
    if not str(target).startswith(str(WEB_ROOT)):
        return None
    if target.suffix not in ALLOWED_EXTENSIONS:
        return None
    return target if target.exists() else None
```

- [ ] **Add seven new command endpoints to `do_POST` in `DigestHandler`**

After the `add-checkin` block and before the `sync/push` block, insert:

```python
            if parsed.path == "/api/v1/commands/set-importance":
                node = store.set_importance(payload["nodeId"], payload.get("importance"))
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/set-due-date":
                node = store.set_due_date(payload["nodeId"], payload.get("dueDate"))
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/set-tags":
                node = store.set_tags(payload["nodeId"], payload.get("tags", []))
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/move-node-up":
                if not store.get_node(payload["nodeId"]):
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                store.move_up(payload["nodeId"])
                return self._send_json({"ok": True, "node": store.get_node(payload["nodeId"])})

            if parsed.path == "/api/v1/commands/move-node-down":
                if not store.get_node(payload["nodeId"]):
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                store.move_down(payload["nodeId"])
                return self._send_json({"ok": True, "node": store.get_node(payload["nodeId"])})

            if parsed.path == "/api/v1/commands/indent-node":
                node = store.indent(payload["nodeId"])
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/unindent-node":
                node = store.unindent(payload["nodeId"])
                return self._send_json({"ok": True, "node": node})
```

- [ ] **Add ValueError to the except block**

The existing except block catches `KeyError` and `Exception`. Add `ValueError` between them so indent/unindent errors return 400:

```python
        except KeyError as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
```

- [ ] **Smoke test**
```bash
cd /Users/kerry/gist && PYTHONPATH=. python3 -m digest.api &
sleep 1
curl -s http://127.0.0.1:8787/health
curl -s "http://127.0.0.1:8787/api/v1/bootstrap" | python3 -c "import sys,json; d=json.load(sys.stdin); print('nodeOrder count:', len(d['nodeOrder']))"
kill %1 2>/dev/null; true
```
Expected: `{"ok": true}` and a nodeOrder count matching your node count.

- [ ] **Commit**
```bash
git add digest/api.py
git commit -m "feat: fix asset serving, add 7 new API command endpoints"
```

---

## Task 9: Wire new mutations in app.js

**Files:**
- Modify: `web/app.js`

- [ ] **Add new cases to `applyMutationLocally`**

In `applyMutationLocally`, the function begins with the add-child/add-sibling block (which returns early), then reaches `const node = nodeById(mutation.nodeId)` followed by `if (!node) return`. After the existing rename/complete/archive blocks, add:

```js
  if (mutation.type === "set-importance") node.importance = mutation.importance ?? null;
  if (mutation.type === "set-due-date") node.dueDate = mutation.dueDate ?? null;
  if (mutation.type === "set-tags") node.tags = mutation.tags ?? [];

  if (mutation.type === "move-node-up") {
    const siblings = state.nodes
      .filter((n) => n.parentId === node.parentId && n.status !== "archived")
      .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0));
    const idx = siblings.findIndex((n) => n.id === node.id);
    if (idx > 0) {
      const tmp = siblings[idx - 1].sortIndex;
      siblings[idx - 1].sortIndex = node.sortIndex;
      node.sortIndex = tmp;
    }
  }
  if (mutation.type === "move-node-down") {
    const siblings = state.nodes
      .filter((n) => n.parentId === node.parentId && n.status !== "archived")
      .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0));
    const idx = siblings.findIndex((n) => n.id === node.id);
    if (idx < siblings.length - 1) {
      const tmp = siblings[idx + 1].sortIndex;
      siblings[idx + 1].sortIndex = node.sortIndex;
      node.sortIndex = tmp;
    }
  }
  if (mutation.type === "indent-node") {
    const siblings = state.nodes
      .filter((n) => n.parentId === node.parentId && n.status !== "archived")
      .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0));
    const idx = siblings.findIndex((n) => n.id === node.id);
    if (idx > 0) {
      const newParent = siblings[idx - 1];
      node.parentId = newParent.id;
      node.type = childType(newParent.type);
    }
  }
  if (mutation.type === "unindent-node") {
    const parent = nodeById(node.parentId);
    if (parent) {
      node.parentId = parent.parentId ?? null;
      const grandparent = parent.parentId ? nodeById(parent.parentId) : null;
      node.type = childType(grandparent?.type ?? "root");
    }
  }
```

- [ ] **Add new cases to `replayMutation`**

After the `archive-node` block and before the final `throw new Error`:

```js
  if (mutation.type === "set-importance") {
    return api("/api/v1/commands/set-importance", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId, importance: mutation.importance }),
    });
  }
  if (mutation.type === "set-due-date") {
    return api("/api/v1/commands/set-due-date", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId, dueDate: mutation.dueDate }),
    });
  }
  if (mutation.type === "set-tags") {
    return api("/api/v1/commands/set-tags", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId, tags: mutation.tags }),
    });
  }
  if (mutation.type === "move-node-up") {
    return api("/api/v1/commands/move-node-up", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
  if (mutation.type === "move-node-down") {
    return api("/api/v1/commands/move-node-down", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
  if (mutation.type === "indent-node") {
    return api("/api/v1/commands/indent-node", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
  if (mutation.type === "unindent-node") {
    return api("/api/v1/commands/unindent-node", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
```

- [ ] **Commit**
```bash
git add web/app.js
git commit -m "feat: wire 7 new mutation types through applyMutationLocally and replayMutation"
```

---

## Task 10: Add card UI for new node actions

**Files:**
- Modify: `web/app.js`
- Modify: `web/styles.css`

- [ ] **Replace the card template in `renderList`**

Replace the `.map((node) => ...)` callback inside `renderList` with:

```js
  els.list.innerHTML = nodes
    .map(
      (node) => `
        <article class="card ${escapeHtml(node.status)}" data-id="${node.id}">
          <div class="card-header">
            <div>
              <div class="card-title">${badgeFor(node.type)} ${escapeHtml(node.title)}${node.status === "completed" ? " ✓" : ""}</div>
              <div class="card-subtitle">${escapeHtml(node.status)} · ${escapeHtml(node.dueDate || "no due date")} · imp:${node.importance ?? "—"} · ${childrenOf(node.id).length} children</div>
              ${node.tags && node.tags.length ? `<div class="card-tags">${node.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
            </div>
            <button class="icon-button" data-open="${node.id}">Open</button>
          </div>
          <div class="card-actions">
            <button class="action-button" data-rename="${node.id}">Rename</button>
            <button class="action-button" data-complete="${node.id}">Done</button>
            <button class="action-button" data-archive="${node.id}">Archive</button>
            <button class="action-button" data-move-up="${node.id}">↑</button>
            <button class="action-button" data-move-down="${node.id}">↓</button>
            <button class="action-button" data-indent="${node.id}">→</button>
            <button class="action-button" data-unindent="${node.id}">←</button>
            <button class="action-button" data-edit-details="${node.id}">⋯</button>
          </div>
          <div class="card-detail-panel hidden" id="detail-${node.id}">
            <div class="detail-row">
              <label>Importance</label>
              <div class="importance-picker">
                ${[1,2,3,4,5].map((n) => `<button class="imp-btn${node.importance === n ? " active" : ""}" data-imp="${node.id}" data-val="${n}">${n}</button>`).join("")}
                <button class="imp-btn" data-imp="${node.id}" data-val="">—</button>
              </div>
            </div>
            <div class="detail-row">
              <label>Due date</label>
              <input class="detail-input" type="text" placeholder="YYYY, YYYY-MM, or YYYY-MM-DD" data-due="${node.id}" value="${escapeHtml(node.dueDate || "")}">
            </div>
            <div class="detail-row">
              <label>Tags</label>
              <input class="detail-input" type="text" placeholder="comma-separated" data-tags="${node.id}" value="${escapeHtml((node.tags || []).join(", "))}">
            </div>
          </div>
        </article>
      `
    )
    .join("");
```

- [ ] **Add event listeners for new actions after existing listeners in `renderList`**

After the `data-archive` listener block:

```js
  els.list.querySelectorAll("[data-move-up]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-move-up");
      if (id) await queueMutation({ id: generateId(), type: "move-node-up", nodeId: id });
    });
  });
  els.list.querySelectorAll("[data-move-down]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-move-down");
      if (id) await queueMutation({ id: generateId(), type: "move-node-down", nodeId: id });
    });
  });
  els.list.querySelectorAll("[data-indent]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-indent");
      if (id) await queueMutation({ id: generateId(), type: "indent-node", nodeId: id });
    });
  });
  els.list.querySelectorAll("[data-unindent]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-unindent");
      if (id) await queueMutation({ id: generateId(), type: "unindent-node", nodeId: id });
    });
  });
  els.list.querySelectorAll("[data-edit-details]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-edit-details");
      const panel = document.getElementById(`detail-${id}`);
      if (panel) panel.classList.toggle("hidden");
    });
  });
  els.list.querySelectorAll("[data-imp]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-imp");
      const val = btn.getAttribute("data-val");
      const importance = val === "" ? null : parseInt(val, 10);
      if (id) await queueMutation({ id: generateId(), type: "set-importance", nodeId: id, importance });
    });
  });
  els.list.querySelectorAll("[data-due]").forEach((input) => {
    input.addEventListener("change", async () => {
      const id = input.getAttribute("data-due");
      const dueDate = input.value.trim() || null;
      if (id) await queueMutation({ id: generateId(), type: "set-due-date", nodeId: id, dueDate });
    });
  });
  els.list.querySelectorAll("[data-tags]").forEach((input) => {
    input.addEventListener("change", async () => {
      const id = input.getAttribute("data-tags");
      const tags = input.value.split(",").map((t) => t.trim()).filter(Boolean);
      if (id) await queueMutation({ id: generateId(), type: "set-tags", nodeId: id, tags });
    });
  });
```

- [ ] **Append new styles to `web/styles.css`**

```css
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.4rem;
}

.tag {
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  font-size: 0.78rem;
}

.card-detail-panel {
  border-top: 1px solid var(--line);
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  display: grid;
  gap: 0.75rem;
}

.card-detail-panel.hidden {
  display: none;
}

.detail-row {
  display: grid;
  gap: 0.4rem;
}

.detail-row label {
  font-size: 0.8rem;
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.importance-picker {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.imp-btn {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  padding: 0.4rem 0.7rem;
  cursor: pointer;
  font: inherit;
}

.imp-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.detail-input {
  width: 100%;
}
```

- [ ] **Commit**
```bash
git add web/app.js web/styles.css
git commit -m "feat: add move, indent, importance, due date, tags UI to node cards"
```

---

## Task 11: Deployment scripts

**Files:**
- Create: `bin/digest-serve.sh`
- Create: `bin/digest-backup.sh`
- Create: `docs/tailscale-serve.md`

- [ ] **Create `bin/digest-serve.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec PYTHONPATH="$ROOT" python3 -m digest.api --host 127.0.0.1 --port 8787 --no-next-free
```

```bash
chmod +x /Users/kerry/gist/bin/digest-serve.sh
```

- [ ] **Create `bin/digest-backup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DIGEST_BACKUP_DIR:-$HOME/backups/digest}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/digest-$STAMP.db"
sqlite3 "$ROOT/digest.db" ".backup '$OUT'"
echo "backed up to $OUT"
```

```bash
chmod +x /Users/kerry/gist/bin/digest-backup.sh
```

- [ ] **Create `docs/tailscale-serve.md`**

```markdown
# Tailscale Serve Setup for Digest

Expose the Digest API server inside your tailnet only.

## Prerequisites

- Tailscale installed and authenticated on the host machine
- Digest server running on 127.0.0.1:8787 via bin/digest-serve.sh

## Expose

Run once on the host:

    tailscale serve --bg 8787

This creates a private HTTPS endpoint at https://<machine-name>.<tailnet>.ts.net
proxying to http://127.0.0.1:8787.

## Verify

    tailscale serve status

Port 8787 should appear as served over HTTPS.

## Access from any tailnet device

Open https://<machine-name>.<tailnet>.ts.net in a browser.
Install as a PWA for offline-capable mobile access.

## Remove

    tailscale serve --bg --set-raw off

## Notes

- Only reachable from devices on your tailnet. No public internet exposure.
- The PWA caches assets on first load and boots offline when the tailnet is down.
- Schedule bin/digest-backup.sh via cron or launchd for periodic SQLite backups.
```

- [ ] **Smoke test serve**
```bash
/Users/kerry/gist/bin/digest-serve.sh &
sleep 1
curl -s http://127.0.0.1:8787/health
kill %1 2>/dev/null; true
```
Expected: `{ "ok": true }`.

- [ ] **Smoke test backup**
```bash
/Users/kerry/gist/bin/digest-backup.sh
ls ~/backups/digest/
```
Expected: a `digest-YYYYMMDD-HHMMSS.db` file exists.

- [ ] **Commit**
```bash
git add bin/digest-serve.sh bin/digest-backup.sh docs/tailscale-serve.md
git commit -m "feat: add digest-serve, digest-backup, tailscale setup docs"
```

---

## Task 12: Bump service worker cache version

**Files:**
- Modify: `web/sw.js`

- [ ] **Bump the cache version**

Change line 1 of `web/sw.js`:

From: `const CACHE = "digest-shell-v2";`
To:   `const CACHE = "digest-shell-v3";`

- [ ] **Commit**
```bash
git add web/sw.js
git commit -m "chore: bump service worker cache to v3"
```

---

## Spec Coverage Checklist

- [x] Bug 1: XSS in renderFocusCard — Task 1
- [x] Bug 2: Mutation dequeue — Task 1
- [x] Bug 3: visibleNodes index scope — Task 1
- [x] _row_to_node extracted — Task 3
- [x] get_node direct SQL — Task 3
- [x] find_active_matches direct SQL — Task 3
- [x] rename_node direct SQL — Task 4
- [x] set_node_status direct SQL — Task 4
- [x] add_node direct SQL — Task 4
- [x] bootstrap_payload double-load fixed — Task 4
- [x] nodeOrder populated in bootstrap — Task 4
- [x] set_importance, set_due_date, set_tags — Task 5
- [x] move_up, move_down — Task 6
- [x] indent, unindent, type_for_depth — Task 7
- [x] Asset serving extension allowlist — Task 8
- [x] 7 new API endpoints — Task 8
- [x] ValueError returns 400 — Task 8
- [x] 7 new mutation types in applyMutationLocally — Task 9
- [x] 7 new mutation types in replayMutation — Task 9
- [x] Card UI: move/indent/unindent/details — Task 10
- [x] Card UI: importance picker, due date, tags — Task 10
- [x] Values panel unchanged (read-only) — no task needed
- [x] digest-serve.sh — Task 11
- [x] digest-backup.sh — Task 11
- [x] tailscale-serve.md — Task 11
- [x] SW cache bump — Task 12
