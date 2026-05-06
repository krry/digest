from __future__ import annotations

import contextlib
import copy
import datetime
import json
import pathlib
import secrets
import sqlite3
import threading
from typing import Any

from digest.paths import (
    CHECKINS_EXAMPLE_JSON,
    CHECKINS_JSON,
    DB_PATH,
    GOALS_EXAMPLE_JSON,
    GOALS_JSON,
    VALUES_EXAMPLE_JSON,
    VALUES_JSON,
)


DEFAULT_GOALS = {"version": 1, "nodes": []}
DEFAULT_VALUES = {"version": 1, "establishedAt": None, "values": []}
DEFAULT_CHECKINS = {"version": 1, "checkins": []}
BADGES = {"goal": "G", "idea": "I", "step": "S", "task": "T", "free": "·"}
VALID_TYPES = ("goal", "idea", "step", "task", "free")
VALID_STATUSES = ("active", "completed", "archived")
TYPE_FOR_DEPTH = ["goal", "idea", "step", "task"]


def type_for_depth(depth: int) -> str:
    return TYPE_FOR_DEPTH[depth] if depth < len(TYPE_FOR_DEPTH) else "free"


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return secrets.token_hex(3)


def badge_for(node_type: str) -> str:
    return BADGES.get(node_type, "·")


class DigestStore:
    def __init__(
        self,
        db_path: pathlib.Path = DB_PATH,
        goals_path: pathlib.Path = GOALS_JSON,
        values_path: pathlib.Path = VALUES_JSON,
        checkins_path: pathlib.Path = CHECKINS_JSON,
    ):
        self.db_path = db_path
        self.goals_path = goals_path
        self.values_path = values_path
        self.checkins_path = checkins_path
        self._initialized = False
        self._init_lock = threading.Lock()

    def ensure_ready(self):
        with self._init_lock:
            if self._initialized:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as conn:
                self._create_schema(conn)
                if self._is_uninitialized(conn):
                    self._bootstrap_from_json(conn)
            self._initialized = True

    @contextlib.contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_schema(self, conn: sqlite3.Connection):
        conn.executescript(
            """
            create table if not exists meta (
              key text primary key,
              value text not null
            );

            create table if not exists nodes (
              id text primary key,
              type text not null check (type in ('goal', 'idea', 'step', 'task', 'free')),
              title text not null,
              status text not null check (status in ('active', 'completed', 'archived')),
              parent_id text references nodes(id) on delete restrict,
              importance integer check (importance between 1 and 5),
              due_date text,
              tags_json text not null default '[]',
              created_at text not null,
              completed_at text
            );

            create table if not exists node_order (
              node_id text primary key references nodes(id) on delete cascade,
              parent_id text references nodes(id) on delete cascade,
              sort_index integer not null
            );

            create index if not exists node_order_parent_sort_idx on node_order(parent_id, sort_index);
            create index if not exists nodes_parent_id_idx on nodes(parent_id);
            create index if not exists nodes_status_idx on nodes(status);

            create table if not exists values_meta (
              singleton integer primary key check (singleton = 1),
              established_at text
            );

            create table if not exists values_items (
              id integer primary key autoincrement,
              phrase text not null,
              pinned_moment text,
              sort_index integer not null
            );

            create table if not exists checkins (
              id integer primary key autoincrement,
              checkin_date text not null,
              payload_json text not null
            );
            """
        )
        conn.commit()

    def _is_uninitialized(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute("select value from meta where key = 'initialized'").fetchone()
        return row is None

    def _mark_initialized(self, conn: sqlite3.Connection):
        conn.execute(
            "insert or replace into meta(key, value) values('initialized', '1')"
        )

    def _read_json_or_example(self, live_path: pathlib.Path, example_path: pathlib.Path, default: dict) -> dict:
        if live_path.exists():
            return json.loads(live_path.read_text())
        if example_path.exists():
            return json.loads(example_path.read_text())
        return copy.deepcopy(default)

    def _bootstrap_from_json(self, conn: sqlite3.Connection):
        goals = self._read_json_or_example(self.goals_path, GOALS_EXAMPLE_JSON, DEFAULT_GOALS)
        values = self._read_json_or_example(self.values_path, VALUES_EXAMPLE_JSON, DEFAULT_VALUES)
        checkins = self._read_json_or_example(self.checkins_path, CHECKINS_EXAMPLE_JSON, DEFAULT_CHECKINS)
        self._import_snapshot(conn, goals, values, checkins)
        self._mark_initialized(conn)
        conn.commit()

    def _normalize_node(self, node: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "id": node["id"],
            "type": node.get("type") or "free",
            "title": node.get("title") or "",
            "status": node.get("status") or "active",
            "parentId": node.get("parentId"),
            "importance": node.get("importance"),
            "dueDate": node.get("dueDate"),
            "tags": list(node.get("tags") or []),
            "createdAt": node.get("createdAt") or now_utc(),
            "completedAt": node.get("completedAt"),
        }
        if normalized["type"] not in VALID_TYPES:
            raise ValueError(f"Invalid node type: {normalized['type']}")
        if normalized["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid node status: {normalized['status']}")
        return normalized

    def _import_snapshot(
        self,
        conn: sqlite3.Connection,
        goals: dict[str, Any],
        values: dict[str, Any],
        checkins: dict[str, Any],
    ):
        conn.execute("pragma foreign_keys = off")
        conn.execute("delete from node_order")
        conn.execute("delete from nodes")
        conn.execute("pragma foreign_keys = on")
        conn.execute("delete from values_items")
        conn.execute("delete from values_meta")
        conn.execute("delete from checkins")

        order_by_parent: dict[str | None, int] = {}
        for raw_node in goals.get("nodes", []):
            node = self._normalize_node(raw_node)
            conn.execute(
                """
                insert into nodes(
                  id, type, title, status, parent_id, importance, due_date, tags_json, created_at, completed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node["id"],
                    node["type"],
                    node["title"],
                    node["status"],
                    node["parentId"],
                    node["importance"],
                    node["dueDate"],
                    json.dumps(node["tags"]),
                    node["createdAt"],
                    node["completedAt"],
                ),
            )
            sort_index = order_by_parent.get(node["parentId"], 0)
            order_by_parent[node["parentId"]] = sort_index + 1
            conn.execute(
                "insert into node_order(node_id, parent_id, sort_index) values (?, ?, ?)",
                (node["id"], node["parentId"], sort_index),
            )

        established_at = values.get("establishedAt")
        conn.execute(
            "insert into values_meta(singleton, established_at) values (1, ?)",
            (established_at,),
        )
        for index, item in enumerate(values.get("values", [])):
            conn.execute(
                "insert into values_items(phrase, pinned_moment, sort_index) values (?, ?, ?)",
                (item.get("phrase") or "", item.get("pinnedMoment"), index),
            )

        for entry in checkins.get("checkins", []):
            payload = dict(entry)
            checkin_date = payload.get("date") or datetime.date.today().isoformat()
            payload["date"] = checkin_date
            conn.execute(
                "insert into checkins(checkin_date, payload_json) values (?, ?)",
                (checkin_date, json.dumps(payload)),
            )

    def import_snapshot(
        self,
        goals: dict[str, Any],
        values: dict[str, Any] | None = None,
        checkins: dict[str, Any] | None = None,
    ):
        self.ensure_ready()
        current_values = values if values is not None else self.load_values_data()
        current_checkins = checkins if checkins is not None else self.load_checkins_data()
        with self.connect() as conn:
            self._import_snapshot(conn, goals, current_values, current_checkins)
            self._mark_initialized(conn)
            conn.commit()
        self.export_json_mirror()

    def _ordered_nodes(self, conn: sqlite3.Connection, parent_id: str | None) -> list[sqlite3.Row]:
        return conn.execute(
            """
            select n.*
            from nodes n
            join node_order o on o.node_id = n.id
            where (
              (? is null and n.parent_id is null)
              or n.parent_id = ?
            )
            order by o.sort_index asc
            """,
            (parent_id, parent_id),
        ).fetchall()

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

    def _export_nodes_preorder(self, conn: sqlite3.Connection, parent_id: str | None, out: list[dict[str, Any]]):
        for row in self._ordered_nodes(conn, parent_id):
            out.append(self._row_to_node(row))
            self._export_nodes_preorder(conn, row["id"], out)

    def load_goals_data(self) -> dict[str, Any]:
        self.ensure_ready()
        with self.connect() as conn:
            nodes: list[dict[str, Any]] = []
            self._export_nodes_preorder(conn, None, nodes)
        return {"version": 1, "nodes": nodes}

    def load_values_data(self) -> dict[str, Any]:
        self.ensure_ready()
        with self.connect() as conn:
            meta = conn.execute("select established_at from values_meta where singleton = 1").fetchone()
            items = conn.execute(
                "select phrase, pinned_moment from values_items order by sort_index asc, id asc"
            ).fetchall()
        return {
            "version": 1,
            "establishedAt": meta["established_at"] if meta else None,
            "values": [
                {"phrase": row["phrase"], "pinnedMoment": row["pinned_moment"]}
                for row in items
            ],
        }

    def load_checkins_data(self) -> dict[str, Any]:
        self.ensure_ready()
        with self.connect() as conn:
            rows = conn.execute(
                "select payload_json from checkins order by checkin_date asc, id asc"
            ).fetchall()
        return {
            "version": 1,
            "checkins": [json.loads(row["payload_json"]) for row in rows],
        }

    def export_json_mirror(self):
        self.goals_path.write_text(json.dumps(self.load_goals_data(), indent=2))
        self.values_path.write_text(json.dumps(self.load_values_data(), indent=2))
        self.checkins_path.write_text(json.dumps(self.load_checkins_data(), indent=2))

    def write_values_data(self, values_data: dict[str, Any]):
        self.ensure_ready()
        goals = self.load_goals_data()
        checkins = self.load_checkins_data()
        with self.connect() as conn:
            self._import_snapshot(conn, goals, values_data, checkins)
            self._mark_initialized(conn)
            conn.commit()
        self.export_json_mirror()

    def append_checkin(self, entry: dict[str, Any]):
        self.ensure_ready()
        payload = dict(entry)
        checkin_date = payload.get("date") or datetime.date.today().isoformat()
        payload["date"] = checkin_date
        with self.connect() as conn:
            conn.execute(
                "insert into checkins(checkin_date, payload_json) values (?, ?)",
                (checkin_date, json.dumps(payload)),
            )
            conn.commit()
        self.export_json_mirror()

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
            conn.execute(
                "insert into node_order(node_id, parent_id, sort_index) values (?, ?, ?)",
                (_id, parent_id, row_idx[0]),
            )
            conn.commit()
            row = conn.execute("select * from nodes where id = ?", (_id,)).fetchone()
        self.export_json_mirror()
        return self._row_to_node(row)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        self.ensure_ready()
        with self.connect() as conn:
            row = conn.execute("select * from nodes where id = ?", (node_id,)).fetchone()
        return self._row_to_node(row) if row else None

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

    def find_active_matches(self, query: str) -> list[dict[str, Any]]:
        self.ensure_ready()
        with self.connect() as conn:
            rows = conn.execute(
                "select * from nodes where status = 'active' and lower(title) like lower(?)",
                (f"%{query}%",),
            ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def recent_checkin_date(self) -> str | None:
        self.ensure_ready()
        with self.connect() as conn:
            row = conn.execute(
                "select checkin_date from checkins order by checkin_date desc, id desc limit 1"
            ).fetchone()
        return row["checkin_date"] if row else None

    def active_nodes(self) -> list[dict[str, Any]]:
        return [node for node in self.load_goals_data()["nodes"] if node["status"] == "active"]

    def render_tree(self, show_all: bool = False) -> str:
        goals = self.load_goals_data()
        nodes = goals["nodes"]
        if not nodes:
            return "Nothing here yet. Try /gist:add to create your first goal."

        by_id = {node["id"]: node for node in nodes}
        children: dict[str | None, list[dict[str, Any]]] = {}
        for node in nodes:
            children.setdefault(node["parentId"], []).append(node)

        lines: list[str] = []

        def render_node(node_id: str, depth: int):
            node = by_id[node_id]
            if node["status"] == "archived" and not show_all:
                return
            indent = "   " * depth
            suffix = " ✓" if node["status"] == "completed" else ""
            lines.append(f"{indent}{badge_for(node['type'])}  {node['title']}{suffix}")
            for child in children.get(node_id, []):
                render_node(child["id"], depth + 1)

        for root in children.get(None, []):
            render_node(root["id"], 0)

        values = self.load_values_data()["values"]
        if values:
            phrases = " · ".join(value["phrase"] for value in values if value.get("phrase"))
            if phrases:
                lines.extend(["", f"Values: {phrases}"])
        return "\n".join(lines)
