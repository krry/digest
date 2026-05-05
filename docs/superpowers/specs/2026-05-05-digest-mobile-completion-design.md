# Digest Mobile Completion Design

Date: 2026-05-05

## Scope

Complete the Digest mobile architecture through all six phases of the original spec. This document records the agreed improvements and additions on top of what is already built.

## What Is Already Built

- SQLite store with full schema (nodes, node_order, values_meta, values_items, checkins)
- JSON import/export roundtrip
- Basic store commands: add_node, rename_node, set_node_status, append_checkin, write_values_data
- stdlib HTTP API: health, bootstrap, nodes, values, checkins, export, add-child, add-sibling, rename, complete, archive, update-values, add-checkin
- PWA shell: IndexedDB persistence, service worker, offline boot, pending mutation queue, focus navigation, breadcrumbs, sort modes, all-level view, values display

## Known Bugs To Fix First

### 1. XSS in renderFocusCard (app.js)
`node.title` is injected raw into innerHTML in the focus card. `renderList` uses `escapeHtml()` but the focus card does not. Fix: wrap `node.title` in `escapeHtml()`.

### 2. Mutation dequeue bug (app.js)
Rename, complete, and archive mutations are queued without an `id` field. The dequeue filter `item.id !== mutation.id` becomes `undefined !== undefined` → `false`, which drops all id-less mutations from the queue at once rather than one at a time. Fix: assign `id: generateId()` to every mutation at queue time.

### 3. visibleNodes index scope bug (app.js)
```js
.filter((node, index) => ...)
.map((node) => ({ ...node, sortIndex: index }))
```
`index` is the filter callback's parameter, not in scope in the map. Fix: `(node, index)` in the map, not the filter.

## Store Refactor (Phase 1 Improvement)

Replace the load-modify-reinsert write pattern with targeted SQL. Every command becomes a transaction touching only the rows it needs, followed by `export_json_mirror()`.

The delete-all-reinsert-all pattern stays only for `import_snapshot` (bulk JSON import) and `export_json_mirror` (full export read).

### Revised Write Methods

All of these replace the current implementations that round-trip through `import_snapshot`:

```python
rename_node(node_id, title)
# UPDATE nodes SET title=? WHERE id=?

set_node_status(node_id, status)
# UPDATE nodes SET status=?, completed_at=? WHERE id=?
# completed_at = now_utc() if status == "completed" else None

set_importance(node_id, importance)
# UPDATE nodes SET importance=? WHERE id=?

set_due_date(node_id, due_date)
# UPDATE nodes SET due_date=? WHERE id=?

set_tags(node_id, tags)
# UPDATE nodes SET tags_json=? WHERE id=?
# tags is a list; serialize to JSON before storing

add_node(type, parent_id, title, node_id=None)
# INSERT into nodes
# INSERT into node_order with sort_index = max(siblings) + 1
# Idempotent: if node_id already exists, return existing node
```

### Sibling Ordering Methods

```python
move_up(node_id)
# Swap sort_index with the previous sibling in node_order
# No-op if already first

move_down(node_id)
# Swap sort_index with the next sibling in node_order
# No-op if already last
```

### Indent / Unindent

Indent makes a node the last child of its previous sibling. Unindent makes a node the next sibling of its current parent. Both operations adjust `parent_id` in `nodes` and `sort_index` in `node_order`.

**Type enforcement:** the type hierarchy is depth-driven.

| Depth | Type |
|-------|------|
| 0     | goal |
| 1     | idea |
| 2     | step |
| 3     | task |
| 4+    | free |

```python
TYPE_FOR_DEPTH = ["goal", "idea", "step", "task"]

def type_for_depth(depth: int) -> str:
    return TYPE_FOR_DEPTH[depth] if depth < len(TYPE_FOR_DEPTH) else "free"
```

Indent and unindent recalculate the node's type based on its new depth. This matches the TUI's existing behavior.

```python
indent(node_id)
# Precondition: node has a previous sibling
# new parent = previous sibling
# new type = type_for_depth(new_depth)
# new sort_index = last child of new parent + 1
# Fails clearly if no previous sibling

unindent(node_id)
# Precondition: node has a parent
# new parent = current parent's parent (None if parent is root)
# new type = type_for_depth(new_depth)
# new sort_index = current parent's sort_index + 1 (insert after parent)
# Re-index subsequent siblings
# Fails clearly if already at root
```

### get_node Direct SQL

Replace `get_node`'s current full-load approach:

```python
get_node(node_id) -> dict | None
# SELECT * FROM nodes WHERE id=?
# Single row query, no full load
```

## API Additions and Fixes

### Bootstrap nodeOrder

`GET /api/v1/bootstrap` currently returns `nodeOrder: []`. Populate it from the database:

```json
"nodeOrder": [
  { "nodeId": "abc", "parentId": "xyz", "sortIndex": 0 },
  ...
]
```

### New Command Endpoints

```
POST /api/v1/commands/set-importance    { nodeId, importance }
POST /api/v1/commands/set-due-date      { nodeId, dueDate }
POST /api/v1/commands/set-tags          { nodeId, tags: [] }
POST /api/v1/commands/move-node-up      { nodeId }
POST /api/v1/commands/move-node-down    { nodeId }
POST /api/v1/commands/indent-node       { nodeId }
POST /api/v1/commands/unindent-node     { nodeId }
```

All follow the existing response shape: `{ ok: true, node: {...} }` or `{ ok: false, error: "..." }`.

### Asset Serving Fix

Replace the hardcoded path→filename dict with an allowlist of extensions:

```python
ALLOWED_EXTENSIONS = {".html", ".css", ".js", ".webmanifest", ".png", ".svg", ".ico"}
```

Serve any file under `WEB_ROOT` whose extension is in the allowlist. Strip the leading `/`, resolve the path, and confirm it is still under `WEB_ROOT` (no traversal). A request for `/` maps to `index.html`.

### sync/push

Remains a stub that returns all mutation IDs as accepted. Document clearly in code that the per-command replay path is the real sync mechanism and this endpoint is plumbing for a future batch mode.

## PWA Additions

### Bug fixes

Apply all three bugs described above.

### New Node Actions

Add to each card's action row:

- **Move up / Move down** — reorder within siblings
- **Indent / Unindent** — reparent in the hierarchy
- **Edit details** — opens an inline panel on the card with:
  - Importance: 1–5 selector (or clear)
  - Due date: text input (YYYY, YYYY-MM, or YYYY-MM-DD)
  - Tags: comma-separated text input

Each action queues a mutation optimistically and syncs as normal.

### New Mutation Types

```js
{ type: "set-importance", nodeId, importance }
{ type: "set-due-date",   nodeId, dueDate }
{ type: "set-tags",       nodeId, tags }
{ type: "move-node-up",   nodeId }
{ type: "move-node-down", nodeId }
{ type: "indent-node",    nodeId }
{ type: "unindent-node",  nodeId }
```

Local application of move/indent/unindent reorders `state.nodes` optimistically. On sync, the authoritative server state replaces it via `fetchBootstrap`.

### Values Panel

Read-only. No changes from current implementation.

### Composer Mode Fix

The `add-sibling` mutation correctly carries `siblingId` pointing to the currently focused node. The child type is derived from the sibling's type, not the focus node's type.

## Deployment (Phase 5)

### bin/digest-serve.sh

Starts the API server. Designed to be called by launchd or screen/tmux.

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec PYTHONPATH="$ROOT" python3 -m digest.api --host 127.0.0.1 --port 8787 --no-next-free
```

### bin/digest-backup.sh

SQLite online backup to a timestamped file.

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DIGEST_BACKUP_DIR:-$HOME/backups/digest}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
sqlite3 "$ROOT/digest.db" ".backup '$DEST/digest-$STAMP.db'"
echo "backed up to $DEST/digest-$STAMP.db"
```

### docs/tailscale-serve.md

Documents the exact commands to expose the server over the tailnet:

```bash
tailscale serve --bg 8787
```

Includes: how to verify, how to remove, note on `tailscale serve status`.

## TUI (Phase 6)

The TUI (`bin/gist-tui`) already imports from `digest.store`. With direct SQL replacing the round-trip pattern, the TUI gains correct behavior for all commands automatically. No TUI code changes are required in this pass.

## Out of Scope

- Check-in UI in the PWA (handled by Claude skills)
- Onboard UI in the PWA (handled by Claude skills)
- Notifications and reminders (future pass)
- Realtime sync / websockets
- Collaborative editing
- Values editing in the PWA (handled by Claude skills via update-values API)
- sync/push batch replay implementation

## Acceptance Criteria

- All three bugs are fixed and verified
- Every store write method uses targeted SQL; no command round-trips through import_snapshot
- All seven new command endpoints work and return correct responses
- Bootstrap response includes populated nodeOrder
- Web asset serving works without a hardcoded path map
- Move-up, move-down, indent, unindent, set-importance, set-due-date, set-tags are all functional in the PWA
- PWA works offline: boots from IndexedDB, queues mutations, replays on reconnect
- Values panel renders correctly (read-only)
- digest-serve.sh starts the server cleanly
- digest-backup.sh produces a valid SQLite backup file
- tailscale-serve.md documents the correct commands
