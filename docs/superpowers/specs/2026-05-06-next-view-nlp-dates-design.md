# Next View + NLP Date Parsing — Design Spec

**Date:** 2026-05-06
**Status:** Approved for implementation

---

## Goal

When you open Digest, show what needs attention now. Natural language dates in the add input make scheduling frictionless.

---

## Feature 1: NLP Date Parsing in the Composer

### Behaviour

When the user submits a title in the composer input, the client scans the text for a recognisable date expression using **chrono-node**. If found:

- The date phrase is stripped from the title string
- The resolved date is stored as `dueDate` on the new node (ISO format: `YYYY-MM-DD`, or `YYYY-MM-DDTHH:mm` if a time is expressed)
- If no time component is present, no time is stored — the due date remains a date string

Examples:
| Input | Stored title | Stored dueDate |
|---|---|---|
| `call dentist tomorrow` | `call dentist` | `2026-05-07` |
| `submit report next Friday` | `submit report` | `2026-05-15` |
| `take meds in 3 days` | `take meds` | `2026-05-09` |
| `team sync` | `team sync` | `null` |

### Implementation

- **Library:** `chrono-node` (ESM, loaded via CDN import or bundled). ~50KB, client-side only.
- **Parse point:** inside the form `submit` handler in `app.js`, before the mutation is queued
- **No server changes** for parsing — the resolved ISO string goes into the existing `set-due-date` / `add-child` mutation payload as `dueDate`
- chrono-node's `parse()` returns an array of results with `index`, `text`, and `date()`. Take the first result; strip `result.text` from the title at `result.index`.
- Reference date for resolution: `new Date()` at submit time

### Edge cases

- No date found → title unchanged, `dueDate: null` — no change to existing behaviour
- Entire title is a date phrase → do not submit (title would be empty); keep the raw string as title instead
- chrono-node may match things like "may" in "I may do this" — accept this as a known limitation for now; the detail panel remains the escape hatch for corrections

---

## Feature 2: Next View (root route)

### What it shows

A flat list of nodes from anywhere in the hierarchy where:

```
dueDate IS NOT NULL
AND dueDate <= today + 7 days
AND status = 'active'
```

Sorted:
1. Overdue first (dueDate < today), oldest first
2. Today
3. Within 7 days, ascending by date
4. Tie-break: importance descending

### Card presentation

Same card component as the hierarchy view. Additionally:

- Due date displayed as a human-readable relative string: "overdue", "today", "tomorrow", "in 3 days", "Fri May 9" — not the raw ISO string
- Overdue cards get a carnelian (`--carnelian`) tint on their due date label
- Tapping a card navigates into it (drills into the node's parent context, same as the hierarchy view)

### Empty state

When no nodes are due within 7 days: ghost card reads "Nothing pressing" with muted text "Add a due date to surface items here."

---

## Feature 3: Routing

### Route model

`state.route` extended from `"main" | "values"` to:

| Route | View |
|---|---|
| `"next"` | Next view (due within 7 days) — **default on open** |
| `"all"` | Full goal hierarchy (current main view) |
| `"values"` | Values overlay (unchanged) |

### Navigation

The footer sort-strip gains a **Next / All toggle** (same `composer-mode-toggle` pill style) replacing nothing — Values link stays. The toggle switches between `"next"` and `"all"`.

```
[ sort ▾ ]  [ Next | All ]  [ Values ]
```

- Default on cold open: `"next"`
- Persisted in `saveState` so the last route is remembered across sessions
- The breadcrumb bar: in `"next"` mode, shows only `GIST` (no drill path). In `"all"` mode, behaves exactly as today.
- The focus stack is untouched when switching routes — so switching to `"all"` and back preserves your place.

### Focus stack behaviour in Next view

- Tapping a card in Next view does **not** modify `focusStack`. Instead it switches route to `"all"` and sets `focusStack` to the path to that node's parent, then opens the node — so you land in context.

---

## Architecture

### New files

None. All changes are in existing files.

### Modified files

| File | Change |
|---|---|
| `web/index.html` | Add Next/All toggle to sort-strip |
| `web/app.js` | NLP parsing in submit handler; `renderNext()` function; route switch logic; relative date formatter |
| `web/styles.css` | `.due-label` and `.due-label--overdue` styles |
| `web/sw.js` | Version bump |

### New functions in app.js

- `parseNaturalDate(rawTitle)` → `{ title: string, dueDate: string|null }` — wraps chrono-node, returns cleaned title and resolved ISO date
- `renderNext()` — queries `state.nodes` for due-within-7, renders flat list with relative date labels
- `relativeDueLabel(dueDateStr)` → `string` — converts ISO date to "overdue" / "today" / "tomorrow" / "in N days" / "Mon May 12"

### No server changes

The existing `set-due-date` mutation and `dueDate` column handle everything. No schema migration needed.

---

## Out of scope

- Push notifications (explicit non-goal)
- Reminders at a specific time of day
- Snooze / dismiss
- Recurring due dates
- Due dates on nodes without explicit user input
