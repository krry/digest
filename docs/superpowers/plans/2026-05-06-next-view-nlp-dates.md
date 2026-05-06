# Next View + NLP Date Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add natural-language due-date parsing to the composer input and a "Next" view that surfaces nodes due within 7 days.

**Architecture:** Three self-contained additions to existing files: (1) `parseNaturalDate()` wraps chrono-node in the composer submit handler to strip date phrases from titles; (2) `renderNext()` queries `state.nodes` for due-within-7 active nodes and renders a flat list; (3) the routing system gains a `"next"` route as the cold-open default, with a Next/All toggle in the sort-strip. No new files, no server changes, no schema migration.

**Tech Stack:** chrono-node (ESM, loaded via importmap + import), vanilla JS, existing mutation queue (set-due-date, add-child).

---

## File Map

| File | What changes |
|---|---|
| `web/index.html` | importmap for chrono-node CDN; Next/All toggle buttons in sort-strip |
| `web/app.js` | `parseNaturalDate()`; `relativeDueLabel()`; `renderNext()`; route logic extended; composer submit uses NLP; `snapshotState` includes `route`; breadcrumb hides path in next mode |
| `web/styles.css` | `.due-label` and `.due-label--overdue` |
| `web/sw.js` | Version bump |

---

## Task 1: Load chrono-node via importmap

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`

- [ ] **Step 1: Add importmap before the module script tag**

In `web/index.html`, directly above the final script tag, add:

```html
    <script type="importmap">
    {
      "imports": {
        "chrono-node": "https://cdn.jsdelivr.net/npm/chrono-node@2/dist/esm/index.js"
      }
    }
    </script>
    <script type="module" src="/app.js"></script>
  </body>
```

- [ ] **Step 2: Add the import to app.js top**

At the top of `web/app.js`, change line 1 from:

```js
import { loadState, saveState } from "/db.js";
```

to:

```js
import { loadState, saveState } from "/db.js";
import * as chrono from "chrono-node";
```

- [ ] **Step 3: Smoke-test in browser console**

Open the app. In DevTools console run:

```js
chrono.parseDate("tomorrow");
```

Expected: a Date object, no 404 errors in the Network tab.

- [ ] **Step 4: Commit**

```bash
git add web/index.html web/app.js
git commit -m "feat: load chrono-node via importmap"
```

---

## Task 2: parseNaturalDate() helper

**Files:**
- Modify: `web/app.js` (add after `nowIso()`, around line 55)

- [ ] **Step 1: Add `parseNaturalDate` after `nowIso()`**

Insert immediately after the closing brace of `nowIso()`:

```js
function parseNaturalDate(rawTitle) {
  const ref = new Date();
  const results = chrono.parse(rawTitle, ref, { forwardDate: true });
  if (!results.length) return { title: rawTitle, dueDate: null };

  const hit = results[0];
  const cleaned = (rawTitle.slice(0, hit.index) + rawTitle.slice(hit.index + hit.text.length)).trim();
  if (!cleaned) return { title: rawTitle, dueDate: null };

  const d = hit.start.date();
  const hasTime = hit.start.isCertain("hour");
  const pad = (n) => String(n).padStart(2, "0");
  const dueDate = hasTime
    ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return { title: cleaned, dueDate };
}
```

- [ ] **Step 2: Verify in browser console**

```js
parseNaturalDate("call dentist tomorrow");
// Expected: { title: "call dentist", dueDate: "2026-05-07" }

parseNaturalDate("team sync");
// Expected: { title: "team sync", dueDate: null }

parseNaturalDate("tomorrow");
// Expected: { title: "tomorrow", dueDate: null }  -- empty cleaned title, raw string kept
```

- [ ] **Step 3: Commit**

```bash
git add web/app.js
git commit -m "feat: parseNaturalDate strips date phrase from title"
```

---

## Task 3: Wire NLP into composer submit

**Files:**
- Modify: `web/app.js`

- [ ] **Step 1: Update the composer submit handler**

Find the `els.composer.addEventListener("submit", ...)` block (~line 906). Replace it entirely with:

```js
els.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = els.composerInput.value.trim();
  if (!raw) return;
  const { title, dueDate } = parseNaturalDate(raw);
  const mutation = {
    id: generateId(),
    nodeId: generateId(),
    createdAt: nowIso(),
    title,
    dueDate: dueDate ?? null,
    type: "add-child",
    parentId: currentFocusId(),
  };
  closeComposer();
  await queueMutation(mutation);
});
```

- [ ] **Step 2: Store dueDate in `applyMutationLocally`**

Find `applyMutationLocally`. In the `add-child` branch, a new node is pushed into `state.nodes`. Change this field:

```js
// Before:
dueDate: null,
// After:
dueDate: mutation.dueDate ?? null,
```

- [ ] **Step 3: Test end-to-end in browser**

1. Type `call dentist tomorrow` in the composer and press Enter.
2. Card title should read `call dentist`.
3. Open the card detail panel (ellipsis button) -- Due date field should show tomorrow in YYYY-MM-DD format.
4. Type `team sync` -- title stays `team sync`, Due date stays empty.

- [ ] **Step 4: Commit**

```bash
git add web/app.js
git commit -m "feat: NLP date parsing in composer submit"
```

---

## Task 4: relativeDueLabel() + CSS styles

**Files:**
- Modify: `web/app.js` (add after `parseNaturalDate`)
- Modify: `web/styles.css`

- [ ] **Step 1: Add `relativeDueLabel` after `parseNaturalDate`**

```js
function relativeDueLabel(dueDateStr) {
  if (!dueDateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dueDateStr.length === 10 ? dueDateStr + "T00:00:00" : dueDateStr);
  due.setHours(0, 0, 0, 0);
  const diffDays = Math.round((due - today) / 86400000);
  if (diffDays < 0) return { text: "overdue", overdue: true };
  if (diffDays === 0) return { text: "today", overdue: false };
  if (diffDays === 1) return { text: "tomorrow", overdue: false };
  if (diffDays <= 7) return { text: `in ${diffDays} days`, overdue: false };
  return { text: due.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }), overdue: false };
}
```

- [ ] **Step 2: Add CSS for due labels**

In `web/styles.css`, find the `.card-subtitle` rule. Add immediately after it:

```css
.due-label {
  font-size: 0.72rem;
  font-family: var(--font-display);
  letter-spacing: 0.04em;
  color: var(--muted);
  padding: 0.1em 0.45em;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.06);
}

.due-label--overdue {
  color: var(--carnelian);
  background: rgba(205, 74, 74, 0.12);
}
```

- [ ] **Step 3: Verify in console (today is 2026-05-06)**

```js
relativeDueLabel("2026-05-05"); // { text: "overdue", overdue: true }
relativeDueLabel("2026-05-06"); // { text: "today", overdue: false }
relativeDueLabel("2026-05-07"); // { text: "tomorrow", overdue: false }
relativeDueLabel("2026-05-10"); // { text: "in 4 days", overdue: false }
```

- [ ] **Step 4: Commit**

```bash
git add web/app.js web/styles.css
git commit -m "feat: relativeDueLabel helper and due-label styles"
```

---

## Task 5: Routing -- next / all / values

**Files:**
- Modify: `web/app.js`
- Modify: `web/index.html`

The current route values are `"main"` and `"values"`. This task extends them to `"next" | "all" | "values"`.

- [ ] **Step 1: Change initial route default**

In the `state` object at the top of `web/app.js`:

```js
// Before:
route: "main",
// After:
route: "next",
```

- [ ] **Step 2: Update valuesBack listener**

Find `els.valuesBack.addEventListener`. Change:

```js
// Before:
state.route = "main";
// After:
state.route = "all";
```

- [ ] **Step 3: Add `route` to `snapshotState()`**

Find `snapshotState()` and add the route field. The full function should be:

```js
function snapshotState() {
  return {
    nodes: state.nodes,
    values: state.values,
    checkins: state.checkins,
    focusStack: state.focusStack,
    pendingMutations: state.pendingMutations,
    syncCursor: state.syncCursor,
    sortMode: state.sortMode,
    viewMode: state.viewMode,
    showCompleted: state.showCompleted,
    route: state.route === "values" ? "all" : state.route,
  };
}
```

- [ ] **Step 4: Add Next/All toggle buttons to sort-strip**

In `web/index.html`, find the sort-strip. After the existing `<div class="composer-mode-toggle">` block (Children/All), add a second pill group:

```html
      <div class="composer-mode-toggle">
        <button id="next-route-button" type="button" class="mode-btn">Next</button>
        <button id="all-route-button" type="button" class="mode-btn">All</button>
      </div>
```

- [ ] **Step 5: Add element refs**

In the `els` object in `web/app.js`, add:

```js
nextRouteButton: document.querySelector("#next-route-button"),
allRouteButton: document.querySelector("#all-route-button"),
```

- [ ] **Step 6: Add route toggle listeners**

After the `els.showCompletedBtn` listener, add:

```js
els.nextRouteButton.addEventListener("click", async () => {
  state.route = "next";
  await persistAndRender();
});
els.allRouteButton.addEventListener("click", async () => {
  state.route = "all";
  await persistAndRender();
});
```

- [ ] **Step 7: Update `renderToggles()`**

Replace the function body:

```js
function renderToggles() {
  els.childrenViewButton.classList.toggle("active", state.viewMode === "children");
  els.allViewButton.classList.toggle("active", state.viewMode === "all");
  els.showCompletedBtn.classList.toggle("active", state.showCompleted);
  els.nextRouteButton.classList.toggle("active", state.route === "next");
  els.allRouteButton.classList.toggle("active", state.route === "all");
  els.sortSelect.value = state.sortMode;
}
```

- [ ] **Step 8: Verify in browser**

Load the app. Sort-strip should show Children/All and Next/All pill groups. Tapping Next/All switches their active state. No errors.

- [ ] **Step 9: Commit**

```bash
git add web/app.js web/index.html
git commit -m "feat: next/all route toggle, default to next on cold open"
```

---

## Task 6: renderNext() -- the Next view

**Files:**
- Modify: `web/app.js`

- [ ] **Step 1: Add `nextNodes()` after `sortedNodes()`**

After the closing brace of `sortedNodes()` (~line 106), insert:

```js
function nextNodes() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const cutoff = new Date(today);
  cutoff.setDate(cutoff.getDate() + 7);

  return state.nodes
    .filter((node) => {
      if (!node.dueDate || node.status !== "active") return false;
      const due = new Date(node.dueDate.length === 10 ? node.dueDate + "T00:00:00" : node.dueDate);
      due.setHours(0, 0, 0, 0);
      return due <= cutoff;
    })
    .sort((a, b) => {
      const aDate = a.dueDate.slice(0, 10);
      const bDate = b.dueDate.slice(0, 10);
      if (aDate !== bDate) return aDate.localeCompare(bDate);
      return (b.importance || 0) - (a.importance || 0);
    });
}
```

- [ ] **Step 2: Add `renderNext()` after `renderList()`**

After the closing brace of `renderList()`:

```js
function renderNext() {
  els.emptyState.classList.add("hidden");
  const nodes = nextNodes();

  if (!nodes.length) {
    const wrap = document.createElement("div");
    wrap.className = "card-wrap";
    const ghost = document.createElement("article");
    ghost.className = "card card--ghost";
    const titleEl = document.createElement("div");
    titleEl.className = "card-title card--ghost-label";
    titleEl.textContent = "Nothing pressing";
    const subtitleEl = document.createElement("div");
    subtitleEl.className = "card-subtitle";
    subtitleEl.style.cssText = "text-align:center;margin-top:0.25rem";
    subtitleEl.textContent = "Add a due date to surface items here.";
    ghost.appendChild(titleEl);
    ghost.appendChild(subtitleEl);
    wrap.appendChild(ghost);
    els.list.textContent = "";
    els.list.appendChild(wrap);
    return;
  }

  els.list.textContent = "";
  nodes.forEach((node) => {
    const label = relativeDueLabel(node.dueDate);

    const wrap = document.createElement("div");
    wrap.className = "card-wrap";

    const card = document.createElement("article");
    card.className = "card " + escapeHtml(node.status);
    card.dataset.id = node.id;
    card.dataset.type = node.type;

    const header = document.createElement("div");
    header.className = "card-header";

    const bodyText = document.createElement("div");
    bodyText.className = "card-body-text";

    const titleEl = document.createElement("div");
    titleEl.className = "card-title";
    titleEl.textContent = node.title;
    bodyText.appendChild(titleEl);

    if (label) {
      const dueEl = document.createElement("span");
      dueEl.className = "due-label" + (label.overdue ? " due-label--overdue" : "");
      dueEl.textContent = label.text;
      bodyText.appendChild(dueEl);
    }

    header.appendChild(bodyText);
    card.appendChild(header);
    wrap.appendChild(card);
    els.list.appendChild(wrap);

    card.addEventListener("click", () => {
      const n = nodeById(card.dataset.id);
      if (!n) return;
      const parentPath = [];
      let cursor = n.parentId;
      while (cursor) {
        const p = nodeById(cursor);
        if (!p) break;
        parentPath.unshift(p.id);
        cursor = p.parentId;
      }
      state.focusStack = [...parentPath, n.id];
      state.route = "all";
      persistAndRender();
    });
  });
}
```

- [ ] **Step 3: Update `render()` to branch on route**

Replace the `render()` function:

```js
function render() {
  renderStatus();
  const onValues = state.route === "values";
  els.valuesPage.classList.toggle("hidden", !onValues);
  if (onValues) {
    renderValues();
    return;
  }
  renderDepthBackground();
  renderBreadcrumbs();
  renderToggles();
  composerPlaceholder();

  if (state.route === "next") {
    els.focusCard.classList.add("hidden");
    els.focusCard.textContent = "";
    renderNext();
  } else {
    renderFocusCard();
    renderList();
  }
}
```

- [ ] **Step 4: Update `renderBreadcrumbs()` for Next mode**

At the very top of `renderBreadcrumbs()`, before any existing code, add an early-return guard. The function currently starts with:

```js
function renderBreadcrumbs() {
  const path = pathNodes();
```

Change it to:

```js
function renderBreadcrumbs() {
  if (state.route === "next") {
    const gistColor = syncStatusColor();
    const busy = state.status === "syncing" || state.pendingMutations.length > 0;
    const btn = document.createElement("button");
    btn.className = "crumb" + (busy ? " crumb--spinning" : "");
    btn.setAttribute("data-sync", "");
    btn.style.setProperty("--crumb-color", gistColor);
    btn.textContent = "GIST";
    btn.addEventListener("click", syncIfPossible);
    const label = document.createElement("span");
    label.className = "crumb crumb--current";
    label.style.setProperty("--crumb-color", "rgba(255,255,255,0.4)");
    label.textContent = "Next";
    els.breadcrumbs.textContent = "";
    els.breadcrumbs.appendChild(btn);
    els.breadcrumbs.appendChild(label);
    return;
  }
  const path = pathNodes();
```

- [ ] **Step 5: Test Next view end-to-end**

1. Add a node with `dentist tomorrow` -- title `dentist`, appears in Next view.
2. Empty Next view shows "Nothing pressing / Add a due date to surface items here."
3. Overdue node shows red `overdue` label.
4. Tapping a Next-view card navigates to parent context in All view.
5. Next/All switching preserves focusStack.

- [ ] **Step 6: Commit**

```bash
git add web/app.js
git commit -m "feat: Next view with due-within-7 nodes and relative date labels"
```

---

## Task 7: Composer placeholder + sw.js bump

**Files:**
- Modify: `web/app.js`
- Modify: `web/sw.js`

- [ ] **Step 1: Update `composerPlaceholder()` for next mode**

Find `composerPlaceholder()`. Replace with:

```js
function composerPlaceholder() {
  if (state.route === "next") {
    els.composerInput.placeholder = "Add a goal... (due dates work here too)";
    return;
  }
  const focus = nodeById(currentFocusId());
  els.composerInput.placeholder = focus
    ? `New ${childType(focus.type)}...`
    : "New goal...";
}
```

- [ ] **Step 2: Bump service worker version**

In `web/sw.js`:

```js
// Before:
const CACHE = "digest-shell-v30";
// After:
const CACHE = "digest-shell-v31";
```

- [ ] **Step 3: Final smoke test**

1. Hard-refresh (Cmd+Shift+R) to pick up the new service worker.
2. Cold open defaults to Next view.
3. NLP: `call dentist tomorrow` strips to `call dentist`, stores dueDate, appears in Next.
4. Overdue nodes show red `overdue` pill.
5. Next-view card tap navigates to parent in All mode.
6. Values, Done toggle, sort, and Children/All view mode all still work.

- [ ] **Step 4: Commit**

```bash
git add web/app.js web/sw.js
git commit -m "feat: composer next-mode placeholder, sw v31"
```

---

## Spec Coverage

| Spec requirement | Task |
|---|---|
| chrono-node parses natural language date | Task 1, 2 |
| Date phrase stripped from title | Task 2 |
| Empty-title guard keeps raw string | Task 2 |
| ISO dueDate stored on node | Task 3 |
| Time component only if expressed | Task 2 (isCertain hour) |
| Next view: dueDate <= today+7, status=active | Task 6 nextNodes() |
| Sort: overdue first, ascending, tie-break importance | Task 6 sort |
| Relative labels: overdue/today/tomorrow/in N days/weekday | Task 4 |
| Overdue label carnelian | Task 4 CSS |
| Empty state: "Nothing pressing" | Task 6 renderNext() |
| Tap Next card navigates to parent in All | Task 6 click handler |
| Route model: next/all/values | Task 5 |
| Next/All toggle in sort-strip (pill style) | Task 5 |
| Default cold open: next | Task 5 initial state |
| Route persisted | Task 5 snapshotState |
| Breadcrumb in next mode: GIST + Next only | Task 6 renderBreadcrumbs guard |
| Focus stack preserved when switching routes | Task 5 |
| Tapping Next card sets focusStack to parent path | Task 6 |
| No server changes | confirmed |
| sw.js version bump | Task 7 |
