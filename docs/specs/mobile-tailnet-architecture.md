# Digest Mobile Web + Tailnet Architecture

Date: 2026-05-05

## Summary

Build a mobile-first web client for Digest without introducing a public backend.

This is a single-user system.

The right shape is:

- one canonical datastore on one always-on machine
- one offline-capable local datastore inside the PWA
- a small private API on that machine
- a mobile-first web client served privately over Tailscale
- the existing Textual TUI kept as a first-class client

Tailscale replaces public hosting and public auth. It does not replace the need for one canonical application service.

Because the mobile client must keep working when the tailnet is unavailable, the web app also needs a real local persistence and sync layer.

Treat this as single-user, multi-device sync, not collaborative sync.

## Alignment With The Existing Repo

This spec is aligned to the current repo, not the flat append-only `entries` sketch.

Today the app is:

- a hierarchical node model in `goals.json`
- separate `values.json` and `checkins.json`
- mutable node updates
- soft archive via `status`
- type-aware hierarchy: `goal -> idea -> step -> task -> free`
- command-oriented interaction in the TUI

Assumptions for the web architecture:

- there is only one human user
- multiple personal devices may edit the same data
- occasional offline drift between devices is acceptable
- replay should be deterministic and boring

Current node shape:

```json
{
  "id": "abc123",
  "type": "goal | idea | step | task | free",
  "title": "string",
  "status": "active | completed | archived",
  "parentId": null,
  "importance": null,
  "dueDate": null,
  "tags": [],
  "createdAt": "UTC ISO-8601",
  "completedAt": null
}
```

That model should remain the product truth for v1 of the web client.

## What To Keep From The Earlier Sketch

Keep:

- mobile-first design
- optimistic client updates
- local cache
- offline-first operation
- focus navigation
- private deployment
- no realtime requirement for v1

Discard:

- flat append-only `entries` log
- generic `data jsonb` source-of-truth model
- public Railway or Vercel backend as the canonical store
- direct multi-client writes to shared JSON files

## Why Not Shared JSON

Multiple clients directly reading and writing shared JSON will fail in boring ways:

- concurrent writes
- partial writes
- stale reads
- no locking discipline across clients
- harder recovery after corruption
- poor mobile ergonomics if the source machine is slow or asleep

JSON files are fine as a bootstrap and export format. They are not the right multi-client source of truth.

## Offline-First Requirement

The mobile web app must still be useful when:

- the host machine is asleep
- Tailscale is disconnected
- the phone is on a bad network
- the app is opened in airplane mode

That means the PWA cannot be a simple remote shell over the API.

It needs:

- a local browser datastore
- a queued command log for unsynced writes
- stable client-generated IDs
- replay and reconciliation once connectivity returns

This is still compatible with a private Tailscale-hosted source of truth. It just means the browser becomes a temporary edge node.

Because there is only one user, this does not require collaborative merge logic. It only requires deterministic replay.

## Why Tailscale Is Still The Right Move

Tailscale is a good fit because it gives us private network access and identity without exposing the app publicly.

Use:

- `tailscale serve` to expose the private web service to the tailnet
- tailnet access controls to limit which devices or users can reach it
- Tailscale identity headers on proxied requests if we ever need per-device attribution

Do not use:

- Taildrive as the primary datastore
- Funnel for the app itself unless you explicitly want public internet access

Notes from current docs:

- Tailscale Serve is intended for private tailnet-only service exposure.
- Taildrive is still alpha as of January 5, 2026.

## Target Architecture

```text
iPhone / Android / iPad / laptop browser
            |
  local PWA runtime
    - IndexedDB cache
    - queued commands
    - service worker
            |
            v
   Tailscale private HTTPS when available
            |
            v
   digest host on always-on machine
     - FastAPI app
     - SQLite database
     - optional static web bundle
     - JSON import/export helpers
            |
            v
  existing Textual TUI and shell tools
   talk to same core storage model
```

## Recommendation

Use:

- `SQLite` for canonical data
- `FastAPI` for the private API
- `SvelteKit` for the mobile-first web client
- `tailscale serve` for private access inside the tailnet

Why this stack:

- `SQLite` is enough for a personal app and dramatically safer than shared JSON
- `FastAPI` is tiny and easy to keep honest
- `SvelteKit` is good for a PWA and touch-first UI
- `IndexedDB` gives the PWA real offline persistence
- the whole thing can stay private and local-first
- single-user assumptions keep sync logic simple

## Deployment Topology

One machine in the tailnet becomes the Digest host.

Requirements:

- usually on
- stable local storage
- Tailscale installed
- can run the API and web app continuously

Suggested host options:

- always-on Mac mini
- home Linux box
- small VPS joined to your tailnet

Serve model:

- API listens on `127.0.0.1:8787`
- web app listens on `127.0.0.1:4173` or is served by the API
- `tailscale serve` exposes one HTTPS tailnet URL

Preferred simplification:

- serve the built web app from FastAPI
- keep one private origin
- avoid CORS entirely

Important nuance:

- once installed, the PWA should continue to boot from cached assets even when the tailnet is unavailable
- writes made offline remain local until the app can reach the private API again

## Canonical Storage Schema

### Nodes

```sql
create table nodes (
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

create index nodes_parent_id_idx on nodes(parent_id);
create index nodes_status_idx on nodes(status);
create index nodes_type_idx on nodes(type);
```

Notes:

- `due_date` stays text to preserve current partial-date semantics: `YYYY`, `YYYY-MM`, `YYYY-MM-DD`
- `tags_json` stays a JSON array serialized as text for v1 simplicity
- ordering remains explicit in application logic, not implied by SQL alone

### Sibling Order

The current JSON model preserves order by array position. SQLite needs explicit sibling ordering.

```sql
create table node_order (
  node_id text primary key references nodes(id) on delete cascade,
  parent_id text references nodes(id) on delete cascade,
  sort_index integer not null
);

create index node_order_parent_sort_idx on node_order(parent_id, sort_index);
```

This preserves:

- current manual ordering
- move up/down behavior
- stable tree and Miller column rendering

### Values

```sql
create table values_meta (
  singleton integer primary key check (singleton = 1),
  established_at text
);

create table values_items (
  id integer primary key autoincrement,
  phrase text not null,
  pinned_moment text,
  sort_index integer not null
);
```

### Checkins

```sql
create table checkins (
  id integer primary key autoincrement,
  created_at text not null,
  payload_json text not null default '{}'
);
```

### Optional Event Log

Do not make append-only events the primary model for v1.

If desired later, add an audit/event table for debugging and export:

```sql
create table events (
  id integer primary key autoincrement,
  event_type text not null,
  payload_json text not null,
  created_at text not null
);
```

Useful, but not required for the first mobile client.

## Core Application Layer

Before the web client, introduce one shared storage layer in Python.

Suggested module shape:

```text
digest/
  core/
    models.py
    store.py
    json_store.py
    sqlite_store.py
    commands.py
```

Responsibilities:

- validate node shapes
- enforce allowed types and statuses
- enforce parent/child typing rules
- preserve sibling order
- centralize commands like add, rename, complete, archive, move, indent, unindent

This lets the TUI and API share the same behavior instead of drifting.

## API Shape

Keep the API command-oriented, because that matches the existing app better than generic CRUD.

Base path:

```text
/api/v1
```

### Read Endpoints

```text
GET /api/v1/bootstrap
GET /api/v1/nodes
GET /api/v1/values
GET /api/v1/checkins
GET /api/v1/sync?since=<cursor>
GET /api/v1/export/json
```

`GET /bootstrap` returns enough to render the app fast:

```json
{
  "serverTime": "2026-05-05T12:34:56Z",
  "nodes": [],
  "nodeOrder": [],
  "values": {
    "establishedAt": null,
    "items": []
  },
  "prefs": {
    "defaultView": "columns"
  }
}
```

`GET /sync?since=<cursor>` returns all server-side changes after a known sync point.

Example:

```json
{
  "cursor": "2026-05-05T12:34:56.000001Z",
  "changes": [
    {
      "changeId": "srv_123",
      "clientMutationId": "ios_abc_001",
      "entityType": "node",
      "entityId": "def456",
      "op": "upsert",
      "payload": {
        "id": "def456",
        "type": "step",
        "title": "Call the county office",
        "status": "active",
        "parentId": "abc123",
        "importance": null,
        "dueDate": null,
        "tags": [],
        "createdAt": "2026-05-05T12:34:56Z",
        "completedAt": null
      },
      "createdAt": "2026-05-05T12:34:56Z"
    }
  ]
}
```

This is not full event sourcing. It is a pragmatic sync feed for offline clients.

### Command Endpoints

```text
POST /api/v1/commands/add-child
POST /api/v1/commands/add-sibling
POST /api/v1/commands/rename-node
POST /api/v1/commands/complete-node
POST /api/v1/commands/archive-node
POST /api/v1/commands/move-node-up
POST /api/v1/commands/move-node-down
POST /api/v1/commands/indent-node
POST /api/v1/commands/unindent-node
POST /api/v1/commands/set-importance
POST /api/v1/commands/set-due-date
POST /api/v1/commands/set-tags
POST /api/v1/commands/update-values
POST /api/v1/commands/add-checkin
POST /api/v1/sync/push
```

Example:

```json
POST /api/v1/commands/add-child

{
  "parentId": "abc123",
  "title": "Call the county office"
}
```

Response:

```json
{
  "ok": true,
  "node": {
    "id": "def456",
    "type": "step",
    "title": "Call the county office",
    "status": "active",
    "parentId": "abc123",
    "importance": null,
    "dueDate": null,
    "tags": [],
    "createdAt": "2026-05-05T12:34:56Z",
    "completedAt": null
  }
}
```

This keeps the API aligned with the current mental model of the app.

For offline support, every write request should also carry:

- `clientId`
- `clientMutationId`
- `baseCursor` or `baseVersion`

Example:

```json
POST /api/v1/commands/rename-node

{
  "clientId": "iphone-kerry",
  "clientMutationId": "iphone-kerry-00042",
  "baseCursor": "2026-05-05T12:30:00.000000Z",
  "nodeId": "def456",
  "title": "Call county zoning office"
}
```

`POST /api/v1/sync/push` is the batch form for replaying queued offline mutations:

```json
{
  "clientId": "iphone-kerry",
  "baseCursor": "2026-05-05T12:30:00.000000Z",
  "mutations": [
    {
      "clientMutationId": "iphone-kerry-00042",
      "command": "rename-node",
      "payload": {
        "nodeId": "def456",
        "title": "Call county zoning office"
      }
    }
  ]
}
```

Because this is single-user:

- pushes can be applied in strict client order
- we do not need collaborative merge semantics
- we only need idempotency and clear replay failure handling

## Authentication

For v1, prefer tailnet-private access over API keys.

Options, in order:

1. Only expose the app inside the tailnet with `tailscale serve`
2. Trust tailnet reachability as the access boundary for v1
3. Optionally inspect Tailscale identity headers later if device/user-aware actions become useful

Do not start with:

- public auth providers
- email/password
- OAuth complexity
- exposed internet endpoints

Offline mode note:

- when the app is offline, previously cached local data remains readable and writable
- authentication is effectively “last successful private install and cached session” for v1

That is acceptable here because the app is personal, private, and tailnet-scoped.

## Web Client Shape

Use a mobile-first PWA.

Suggested structure:

```text
web/
  src/
    routes/
      +layout.svelte
      +page.svelte
      node/[id]/+page.svelte
      values/+page.svelte
    lib/
      api/
      stores/
      components/
      gestures/
      utils/
```

Core views:

- Home / root goals
- Focus view for one node and its children
- Quick-add bar
- Search sheet
- Values view
- Check-in view

## Mobile UX Model

Do not try to recreate the full desktop TUI on a phone.

Use:

- one-handed navigation
- stacked focus navigation
- large tap targets
- bottom input bar
- sheet-style overlays

### Recommended Information Architecture

Primary mobile flow:

```text
Goals -> Ideas -> Steps -> Tasks
```

Tap behavior:

- tap a node to focus into it
- swipe back or tap breadcrumb to move up
- long press for node actions

This keeps the spirit of the column browser without forcing Miller columns onto a narrow screen.

## Client State

For v1:

- fetch full bootstrap on load
- keep client state in memory
- persist canonical local cache in IndexedDB
- optimistic updates for write commands
- queue writes while offline
- flush queued writes when the API becomes reachable
- no realtime

State shape:

```ts
type AppState = {
  nodesById: Map<string, Node>
  childrenByParent: Map<string | null, string[]>
  values: ValuesState
  focusStack: string[]
  syncCursor: string | null
  pendingMutations: PendingMutation[]
  lastLoadedAt: string | null
}
```

Derived state:

- current focus node
- current children
- visible breadcrumbs
- filtered search results
- sort order for “all ideas / all steps / all tasks” views
- connectivity state
- sync state

## PWA Requirements

Required:

- installable on iPhone and Android
- service worker for cached shell/assets
- IndexedDB for app state and pending mutations
- graceful offline boot
- visible sync indicator

Useful UI states:

- synced
- pending local changes
- offline
- sync error

The app should feel calm about this. No scary banners unless there is an actual conflict or failed replay.

## Sorting And “All-Level” Views

The web app should preserve the useful new concept from the TUI:

- normal focused child list
- optional all-level type view

Examples:

- All Ideas
- All Steps
- All Tasks

Sorts:

- manual
- title
- created
- status
- importance
- due

This is especially useful on mobile because it gives you a useful flat operational mode without destroying the hierarchy.

## Sync Model

Start simple.

V1 sync:

- on first online install, download bootstrap and persist locally
- on every launch, boot from IndexedDB immediately
- if online, fetch server changes since `syncCursor`
- if offline, keep working from local cache
- every local write is applied optimistically and appended to `pendingMutations`
- when connectivity returns, replay pending mutations in order
- after successful push, pull authoritative server changes and advance `syncCursor`

No websockets yet.

If later needed, add:

- `GET /changes?since=...`
- server event stream

But not in v1.

## Conflict Strategy

Offline support forces us to choose conflict behavior.

V1 recommendation:

- commands are the sync unit, not raw row overwrites
- server applies queued mutations sequentially
- for simple field edits, last successful command wins
- invalid structural operations fail explicitly and return an error
- the client marks failed queued mutations and asks the user to resolve them

Because there is only one user, “conflict” here mostly means:

- the same person edited on two devices before they reconnected
- one device is replaying against a newer server state

This is not a collaborative editing problem.

Examples:

- two clients rename the same node offline: latest accepted rename wins
- one client archives a node while another adds a child under it: server may reject the add-child command as invalid, or auto-unarchive if that becomes a chosen rule later
- two clients reorder siblings concurrently: whichever command lands later wins that slice of order

Do not attempt CRDT-level cleverness in v1.

Use clear command semantics and explicit error handling instead.

### Suggested Replay Rules

Keep replay rules boring:

- add-child / add-sibling:
  - succeed if the referenced parent still exists and is not archived
  - otherwise fail clearly
- rename:
  - succeed if the node still exists
- complete:
  - succeed if the node still exists
- archive:
  - succeed if the node still exists
- move / indent / unindent:
  - succeed if the referenced node and structural neighbors still exist
  - otherwise fail clearly
- set-importance / set-due-date / set-tags:
  - succeed if the node still exists

After any replay batch:

- server returns accepted mutation IDs
- server returns rejected mutation IDs with reasons
- client removes accepted mutations from queue
- client keeps rejected mutations visible for manual retry or discard
- client pulls fresh state

## Migration Plan

### Phase 1: Shared Core

Create a shared Python core that sits under the TUI.

Deliverables:

- common models
- command functions
- `JsonStore`
- tests for command behavior

The TUI still runs on JSON at this stage.

### Phase 2: SQLite Store

Add `SqliteStore` with the same command surface.

Deliverables:

- schema creation
- import from JSON
- export back to JSON
- parity tests: JSON store vs SQLite store

The TUI can switch behind a feature flag or config.

### Phase 3: Private API

Add a FastAPI app that uses `SqliteStore`.

Deliverables:

- bootstrap endpoint
- command endpoints
- sync pull endpoint
- sync push endpoint
- JSON export endpoint
- basic health check

### Phase 4: Web Client

Build the mobile-first PWA.

Deliverables:

- focus navigation
- add / rename / complete / archive
- values view
- check-in flow
- all-level views and sorting
- IndexedDB cache
- service worker
- pending mutation queue
- offline boot and replay

### Phase 5: Tailscale Deployment

Run the API and web app on the Digest host and expose via `tailscale serve`.

Deliverables:

- private HTTPS tailnet URL
- startup scripts
- backup strategy

### Phase 6: TUI Migration

Point the TUI at the shared core backed by SQLite, or at the API if needed.

Preferred:

- TUI talks to the same Python core and local SQLite directly on the host

Optional later:

- remote TUI mode via API

## Backups And Portability

Keep exports dead simple.

Required:

- JSON export matching current repo shape
- JSON import from current repo shape
- periodic SQLite backup

This preserves the project’s local-first character and avoids lock-in.

## Constraints And Tradeoffs

### Pros

- no public backend exposure
- one real source of truth
- local offline operation on mobile
- mobile and TUI stay in parity
- safer than shared JSON
- easy to back up
- single-user assumptions keep sync comprehensible

### Cons

- the host machine must be available
- offline sync adds real complexity
- replay failure handling becomes part of the product
- there is still a backend, just a private one
- you need a migration from JSON to SQLite

## Non-Goals

Not for v1:

- public multi-user app
- complex auth
- collaborative editing
- realtime sync
- append-only event sourcing as the primary model
- direct write access from clients to shared JSON files
- sophisticated CRDT conflict resolution

## Acceptance Criteria

This architecture is successful when:

- the TUI and web client operate on the same canonical data
- the web client works well on a phone, one-handed
- the web client still boots and accepts edits while offline
- offline edits sync correctly once the tailnet comes back
- the app is reachable only inside the tailnet
- node ordering and hierarchy match the current TUI behavior
- values and checkins remain first-class, not afterthoughts
- JSON import/export still works

## Immediate Next Step

Build the shared Python core and SQLite store first.

Do not start with the web UI.

The order should be:

1. shared core
2. SQLite store
3. import/export
4. FastAPI + sync endpoints
5. offline-capable PWA shell and local store
6. mutation queue + replay
7. Tailscale Serve wiring

That path keeps the app coherent and avoids building a pretty client on top of mush.
