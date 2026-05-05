import { loadState, saveState } from "/db.js";

const SORTERS = {
  manual: (a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0),
  title: (a, b) => a.title.localeCompare(b.title),
  created: (a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""),
  status: (a, b) => (a.status || "").localeCompare(b.status || "") || a.title.localeCompare(b.title),
  importance: (a, b) => (b.importance || 0) - (a.importance || 0) || a.title.localeCompare(b.title),
  due: (a, b) => (a.dueDate || "9999").localeCompare(b.dueDate || "9999") || a.title.localeCompare(b.title),
};

const state = {
  nodes: [],
  values: { establishedAt: null, items: [] },
  checkins: [],
  focusStack: [],
  pendingMutations: [],
  syncCursor: null,
  sortMode: "manual",
  viewMode: "children",
  status: "booting",
  detail: "Loading cached state.",
};

let syncInFlight = false;
let retryTimer = null;

const els = {
  statusPill: document.querySelector("#status-pill"),
  statusDetail: document.querySelector("#status-detail"),
  breadcrumbs: document.querySelector("#breadcrumbs"),
  focusCard: document.querySelector("#focus-card"),
  list: document.querySelector("#list"),
  emptyState: document.querySelector("#empty-state"),
  valuesList: document.querySelector("#values-list"),
  valuesCount: document.querySelector("#values-count"),
  composer: document.querySelector("#composer"),
  composerInput: document.querySelector("#composer-input"),
  composerMode: document.querySelector("#composer-mode"),
  syncButton: document.querySelector("#sync-button"),
  childrenViewButton: document.querySelector("#children-view-button"),
  allViewButton: document.querySelector("#all-view-button"),
  sortSelect: document.querySelector("#sort-select"),
};

function generateId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `digest-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function childType(parentType) {
  return {
    goal: "idea",
    idea: "step",
    step: "task",
    task: "free",
    free: "free",
    root: "goal",
  }[parentType || "root"];
}

function badgeFor(type) {
  return {
    goal: "G",
    idea: "I",
    step: "S",
    task: "T",
    free: "·",
  }[type] || "·";
}

function currentFocusId() {
  return state.focusStack[state.focusStack.length - 1] ?? null;
}

function nodeById(id) {
  return state.nodes.find((node) => node.id === id) ?? null;
}

function childrenOf(parentId) {
  return state.nodes
    .filter((node) => node.parentId === parentId && node.status !== "archived")
    .map((node, index) => ({ ...node, sortIndex: index }));
}

function visibleNodes() {
  const focusId = currentFocusId();
  if (state.viewMode === "all") {
    const focus = nodeById(focusId);
    const type = childType(focus?.type);
    return state.nodes
      .filter((node) => node.type === type && node.status !== "archived")
      .map((node, index) => ({ ...node, sortIndex: index }));
  }
  return childrenOf(focusId);
}

function sortedNodes(nodes) {
  return [...nodes].sort(SORTERS[state.sortMode] || SORTERS.manual);
}

function pathNodes() {
  const path = [];
  let cursor = currentFocusId();
  while (cursor) {
    const node = nodeById(cursor);
    if (!node) break;
    path.unshift(node);
    cursor = node.parentId;
  }
  return path;
}

function setStatus(status, detail) {
  state.status = status;
  state.detail = detail;
  renderStatus();
}

function renderStatus() {
  const pending = state.pendingMutations.length;
  const label = pending > 0 ? `${state.status} · ${pending} pending` : state.status;
  els.statusPill.textContent = label;
  els.statusDetail.textContent = state.detail;
}

function renderBreadcrumbs() {
  const crumbs = [`<button class="crumb ${currentFocusId() ? "" : "active"}" data-focus="">Goals</button>`];
  for (const node of pathNodes()) {
    crumbs.push(`<span class="muted">/</span>`);
    crumbs.push(`<button class="crumb ${node.id === currentFocusId() ? "active" : ""}" data-focus="${node.id}">${node.title}</button>`);
  }
  els.breadcrumbs.innerHTML = crumbs.join("");
  els.breadcrumbs.querySelectorAll("[data-focus]").forEach((button) => {
    button.addEventListener("click", () => {
      const focus = button.getAttribute("data-focus");
      if (!focus) {
        state.focusStack = [];
      } else {
        state.focusStack = pathNodes().map((node) => node.id);
        while (state.focusStack[state.focusStack.length - 1] !== focus) state.focusStack.pop();
      }
      persistAndRender();
    });
  });
}

function renderFocusCard() {
  const node = nodeById(currentFocusId());
  if (!node) {
    els.focusCard.classList.add("hidden");
    els.focusCard.innerHTML = "";
    return;
  }
  els.focusCard.classList.remove("hidden");
  els.focusCard.innerHTML = `
    <div class="focus-meta">
      <span>${badgeFor(node.type)}</span>
      <span>${escapeHtml(node.status)}</span>
      <span>${childrenOf(node.id).length} children</span>
    </div>
    <h2 class="focus-title">${escapeHtml(node.title)}</h2>
  `;
}

function renderList() {
  const nodes = sortedNodes(visibleNodes());
  els.emptyState.classList.toggle("hidden", nodes.length > 0);
  els.list.innerHTML = nodes
    .map(
      (node) => `
        <article class="card ${node.status}">
          <div class="card-header">
            <div>
              <div class="card-title">${badgeFor(node.type)} ${escapeHtml(node.title)}${node.status === "completed" ? " ✓" : ""}</div>
              <div class="card-subtitle">${node.status} · ${node.dueDate || "no due date"} · ${childrenOf(node.id).length} children</div>
            </div>
            <button class="icon-button" data-open="${node.id}">Open</button>
          </div>
          <div class="card-actions">
            <button class="action-button" data-rename="${node.id}">Rename</button>
            <button class="action-button" data-complete="${node.id}">Done</button>
            <button class="action-button" data-archive="${node.id}">Archive</button>
          </div>
        </article>
      `
    )
    .join("");

  els.list.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.getAttribute("data-open");
      if (!id) return;
      const path = pathNodes().map((node) => node.id);
      state.focusStack = [...path, id];
      persistAndRender();
    });
  });

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

  els.list.querySelectorAll("[data-complete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-complete");
      if (!id) return;
      await queueMutation({ id: generateId(), type: "complete-node", nodeId: id });
    });
  });

  els.list.querySelectorAll("[data-archive]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-archive");
      if (!id) return;
      await queueMutation({ id: generateId(), type: "archive-node", nodeId: id });
    });
  });
}

function renderValues() {
  const items = state.values.items || [];
  els.valuesCount.textContent = `${items.length} pinned`;
  els.valuesList.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="value-item">
              <strong>${escapeHtml(item.phrase)}</strong>
              <p class="muted">${escapeHtml(item.pinnedMoment || "")}</p>
            </div>
          `
        )
        .join("")
    : `<p class="muted">No values saved yet.</p>`;
}

function renderToggles() {
  els.childrenViewButton.classList.toggle("active", state.viewMode === "children");
  els.allViewButton.classList.toggle("active", state.viewMode === "all");
  els.sortSelect.value = state.sortMode;
}

function composerPlaceholder() {
  const focus = nodeById(currentFocusId());
  const target =
    els.composerMode.value === "sibling"
      ? focus?.parentId
        ? `Sibling beside ${focus.title}`
        : "Another root goal"
      : focus
        ? `${childType(focus.type)} under ${focus.title}`
        : "A new root goal";
  els.composerInput.placeholder = target;
}

async function persistAndRender() {
  await saveState(snapshotState());
  render();
}

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
  };
}

function render() {
  renderStatus();
  renderBreadcrumbs();
  renderFocusCard();
  renderList();
  renderValues();
  renderToggles();
  composerPlaceholder();
}

function applyMutationLocally(mutation) {
  if (mutation.type === "add-child" || mutation.type === "add-sibling") {
    const focus = mutation.parentId ? nodeById(mutation.parentId) : null;
    const sibling = mutation.siblingId ? nodeById(mutation.siblingId) : null;
    const parentId = mutation.type === "add-sibling" ? sibling?.parentId ?? null : mutation.parentId ?? null;
    const parentType = mutation.type === "add-sibling" ? sibling?.type ?? "goal" : focus?.type ?? "root";
    state.nodes.push({
      id: mutation.nodeId,
      type: mutation.type === "add-sibling" ? sibling?.type ?? "goal" : childType(parentType),
      title: mutation.title,
      status: "active",
      parentId,
      importance: null,
      dueDate: null,
      tags: [],
      createdAt: mutation.createdAt,
      completedAt: null,
    });
    if (mutation.type === "add-child") state.focusStack = [...pathNodes().map((node) => node.id), mutation.nodeId];
    return;
  }

  const node = nodeById(mutation.nodeId);
  if (!node) return;
  if (mutation.type === "rename-node") node.title = mutation.title;
  if (mutation.type === "complete-node") {
    node.status = "completed";
    node.completedAt = nowIso();
  }
  if (mutation.type === "archive-node") {
    node.status = "archived";
    if (currentFocusId() === node.id) state.focusStack.pop();
  }
}

async function queueMutation(mutation) {
  applyMutationLocally(mutation);
  state.pendingMutations.push(mutation);
  setStatus("local", "Saved locally. Waiting to sync.");
  await persistAndRender();
  await syncIfPossible();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchBootstrap() {
  const payload = await api("/api/v1/bootstrap");
  state.nodes = payload.nodes || [];
  state.values = payload.values || { establishedAt: null, items: [] };
  state.checkins = payload.checkins || [];
  state.syncCursor = payload.syncCursor || payload.serverTime || null;
  state.focusStack = state.focusStack.filter((id) => state.nodes.some((node) => node.id === id));
  setStatus("synced", "Fresh state loaded from the host.");
  await persistAndRender();
}

async function replayMutation(mutation) {
  if (mutation.type === "add-child") {
    return api("/api/v1/commands/add-child", {
      method: "POST",
      body: JSON.stringify({
        parentId: mutation.parentId,
        title: mutation.title,
        nodeId: mutation.nodeId,
      }),
    });
  }
  if (mutation.type === "add-sibling") {
    return api("/api/v1/commands/add-sibling", {
      method: "POST",
      body: JSON.stringify({
        nodeId: mutation.siblingId,
        title: mutation.title,
        newNodeId: mutation.nodeId,
      }),
    });
  }
  if (mutation.type === "rename-node") {
    return api("/api/v1/commands/rename-node", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId, title: mutation.title }),
    });
  }
  if (mutation.type === "complete-node") {
    return api("/api/v1/commands/complete-node", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
  if (mutation.type === "archive-node") {
    return api("/api/v1/commands/archive-node", {
      method: "POST",
      body: JSON.stringify({ nodeId: mutation.nodeId }),
    });
  }
  throw new Error(`Unknown mutation: ${mutation.type}`);
}

async function syncIfPossible() {
  if (syncInFlight) return;
  syncInFlight = true;
  try {
    setStatus("syncing", "Trying the host.");
    if (state.pendingMutations.length) {
      for (const mutation of [...state.pendingMutations]) {
        await replayMutation(mutation);
        state.pendingMutations = state.pendingMutations.filter((item) => item.id !== mutation.id);
        await saveState(snapshotState());
      }
    }
    await fetchBootstrap();
  } catch (_error) {
    setStatus(
      navigator.onLine ? "host unreachable" : "offline",
      navigator.onLine ? "Working locally until the tailnet comes back." : "You are offline. Changes stay on this device."
    );
    await saveState(snapshotState());
  } finally {
    syncInFlight = false;
  }
}

function maybeSyncSoon() {
  if (retryTimer) window.clearTimeout(retryTimer);
  retryTimer = window.setTimeout(() => {
    syncIfPossible();
  }, 300);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function boot() {
  try {
    const cached = await loadState();
    if (cached) {
      Object.assign(state, cached);
      setStatus("cached", "Loaded local state.");
      render();
    } else {
      setStatus("starting", "No cached state yet.");
      render();
    }
    await syncIfPossible();
  } catch (error) {
    console.error("Digest boot failed", error);
    setStatus("error", `Startup failed: ${error?.message || "unknown error"}`);
    render();
  }
}

els.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = els.composerInput.value.trim();
  if (!title) return;
  const focus = nodeById(currentFocusId());
  const mutation = {
    id: generateId(),
    nodeId: generateId(),
    createdAt: nowIso(),
    title,
    type: els.composerMode.value === "sibling" ? "add-sibling" : "add-child",
    parentId: currentFocusId(),
    siblingId: currentFocusId(),
  };
  els.composerInput.value = "";
  await queueMutation(mutation);
});

els.syncButton.addEventListener("click", syncIfPossible);
els.childrenViewButton.addEventListener("click", async () => {
  state.viewMode = "children";
  await persistAndRender();
});
els.allViewButton.addEventListener("click", async () => {
  state.viewMode = "all";
  await persistAndRender();
});
els.sortSelect.addEventListener("change", async () => {
  state.sortMode = els.sortSelect.value;
  await persistAndRender();
});
els.composerMode.addEventListener("change", composerPlaceholder);

window.addEventListener("online", maybeSyncSoon);
window.addEventListener("focus", maybeSyncSoon);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") maybeSyncSoon();
});
window.addEventListener("offline", async () => {
  setStatus("offline", "You are offline. Changes stay on this device.");
  await saveState(snapshotState());
});

window.setInterval(() => {
  if (state.pendingMutations.length || state.status === "host unreachable") {
    syncIfPossible();
  }
}, 15000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

boot();
