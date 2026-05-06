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
  composerMode: "child",
  route: "main",
  status: "booting",
  detail: "Loading cached state.",
};

let syncInFlight = false;
let retryTimer = null;

const els = {
  syncDot: document.querySelector("#sync-dot"),
  valuesPage: document.querySelector("#values-page"),
  valuesBack: document.querySelector("#values-back"),
  navValues: document.querySelector("#nav-values"),
  breadcrumbs: document.querySelector("#breadcrumbs"),
  focusCard: document.querySelector("#focus-card"),
  list: document.querySelector("#list"),
  emptyState: document.querySelector("#empty-state"),
  valuesList: document.querySelector("#values-list"),
  valuesCount: document.querySelector("#values-count"),
  composer: document.querySelector("#composer"),
  composerInput: document.querySelector("#composer-input"),
  composerFab: document.querySelector("#composer-fab"),
  composerModeToggle: document.querySelector("#composer-mode-toggle"),
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
  const btn = els.syncButton;
  const dot = els.syncDot;
  const pending = state.pendingMutations.length;

  // Spinning arrow while syncing or mutations pending
  const busy = state.status === "syncing" || pending > 0;
  btn.classList.toggle("spinning", busy);

  // Dot color: green=synced, yellow=pending/local, red=error/offline, grey=starting
  dot.className = "sync-dot";
  if (state.status === "synced" && pending === 0) dot.classList.add("sync-dot--green");
  else if (state.status === "error" || state.status === "offline") dot.classList.add("sync-dot--red");
  else if (state.status === "starting" || state.status === "booting") { /* grey default */ }
  else dot.classList.add("sync-dot--yellow");
}

const TYPE_PLURAL = { goal: "Goals", idea: "Ideas", step: "Steps", task: "Tasks", free: "Notes" };

const TYPE_COLOR_HEX = { goal: "#34d399", idea: "#60a5fa", step: "#c084fc", task: "#f87171", free: "#94a3b8" };

function crumbColor(type) {
  return TYPE_COLOR_HEX[type] || "rgba(255,255,255,0.6)";
}

function renderBreadcrumbs() {
  const path = pathNodes();
  const focus = path[path.length - 1];
  const listType = focus ? childType(focus.type) : "goal";
  const listLabel = TYPE_PLURAL[listType];
  const listColor = crumbColor(listType);

  const crumbs = [`<button class="crumb" data-focus="" style="--crumb-color: rgba(255,255,255,0.7)">GIST</button>`];
  for (const node of path) {
    const col = crumbColor(node.type);
    crumbs.push(`<button class="crumb" data-focus="${node.id}" style="--crumb-color:${col}">${escapeHtml(node.title)}</button>`);
  }
  crumbs.push(`<span class="crumb crumb--current" style="--crumb-color:${listColor}">${listLabel}</span>`);

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
  els.breadcrumbs.scrollLeft = els.breadcrumbs.scrollWidth;
}

function renderFocusCard() {
  const node = nodeById(currentFocusId());
  if (!node) {
    els.focusCard.classList.add("hidden");
    els.focusCard.innerHTML = "";
    return;
  }
  els.focusCard.classList.remove("hidden");
  els.focusCard.dataset.type = node.type;
  const typeRgb = { goal: "52,211,153", idea: "96,165,250", step: "192,132,252", task: "248,113,113", free: "148,163,184" };
  const rgb = typeRgb[node.type] || typeRgb.free;
  els.focusCard.style.background = `linear-gradient(135deg, rgba(${rgb}, 0.30) 0%, rgba(255,255,255,0.07) 65%)`;
  els.focusCard.innerHTML = `<h2 class="focus-title" data-rename-focus="${node.id}">${escapeHtml(node.title)}</h2>`;
  els.focusCard.querySelector(".focus-title").addEventListener("click", () => {
    const titleEl = els.focusCard.querySelector(".focus-title");
    startRenameFocus(node.id, titleEl);
  });
}

function startRenameFocus(id, titleEl) {
  if (titleEl.querySelector("input")) return;
  const node = nodeById(id);
  if (!node) return;
  const orig = node.title;
  const input = document.createElement("input");
  input.className = "rename-input";
  input.value = orig;
  titleEl.textContent = "";
  titleEl.appendChild(input);
  input.focus();
  input.select();
  let committed = false;
  async function commit() {
    if (committed) return;
    committed = true;
    const title = input.value.trim();
    if (title && title !== orig) {
      await queueMutation({ id: generateId(), type: "rename-node", nodeId: id, title });
    } else {
      renderFocusCard();
    }
  }
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    if (e.key === "Escape") { committed = true; renderFocusCard(); }
  });
  input.addEventListener("blur", commit);
}

function renderList() {
  const nodes = sortedNodes(visibleNodes());
  // Ghost replaces empty state — always hide the static panel
  els.emptyState.classList.add("hidden");

  const focusNode = nodeById(currentFocusId());
  const listType = childType(focusNode?.type);

  els.list.innerHTML = nodes
    .map(
      (node) => {
        const subtitleParts = [];
        if (node.status !== "active") subtitleParts.push(escapeHtml(node.status));
        if (node.dueDate) subtitleParts.push(escapeHtml(node.dueDate));
        const subtitle = subtitleParts.length
          ? `<div class="card-subtitle">${subtitleParts.join(" · ")}</div>` : "";
        const impDot = node.importance != null
          ? `<div class="card-imp" style="--imp:${node.importance}"></div>` : "";
        const tags = node.tags && node.tags.length
          ? `<div class="card-tags">${node.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>` : "";
        return `
        <div class="card-wrap">
          <div class="swipe-reveal swipe-reveal--right"><span class="swipe-icon">✓</span></div>
          <div class="swipe-reveal swipe-reveal--left"><span class="swipe-icon">★</span></div>
          <article class="card ${escapeHtml(node.status)}" data-id="${node.id}" data-type="${node.type}">
            ${impDot}
            <div class="card-header">
              <div class="card-body-text">
                <div class="card-title" data-rename-id="${node.id}">${escapeHtml(node.title)}${node.status === "completed" ? " ✓" : ""}</div>
                ${subtitle}
                ${tags}
              </div>
              <button class="card-menu-btn" data-edit-details="${node.id}">&#x22EF;</button>
            </div>

            <div class="card-detail-panel hidden" id="detail-${node.id}">
              <div class="detail-row">
                <label>Importance</label>
                <div class="importance-picker">
                  ${[1,2,3,4,5].map((n) => `<button class="imp-btn${node.importance === n ? " active" : ""}" data-imp="${node.id}" data-val="${n}">${n}</button>`).join("")}
                  <button class="imp-btn" data-imp="${node.id}" data-val="">&mdash;</button>
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
        </div>`;
      }
    )
    .join("");

  attachCardGestures(els.list);

  // Ghost card — always present, uses the correct child type for this level
  const ghostWrap = document.createElement("div");
  ghostWrap.className = "card-wrap";
  const ghost = document.createElement("article");
  ghost.className = "card card--ghost";
  ghost.innerHTML = `<div class="card-title card--ghost-label">+ add ${listType}</div>`;
  // When list is empty, ghost acts as first child; otherwise it adds a sibling
  ghost.addEventListener("click", () => {
    state.composerMode = nodes.length === 0 ? "child" : "sibling";
    els.composerModeToggle.querySelectorAll(".mode-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.mode === state.composerMode);
    });
    openComposer();
  });
  ghostWrap.appendChild(ghost);
  els.list.appendChild(ghostWrap);

  els.list.querySelectorAll("[data-edit-details]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-edit-details");
      const panel = document.getElementById(`detail-${id}`);
      if (panel) panel.classList.toggle("hidden");
    });
  });
  els.list.querySelectorAll("[data-imp]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
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
}

function attachCardGestures(listEl) {
  const SWIPE_THRESHOLD = 72;
  const LONG_PRESS_MS = 400;
  let g = null;
  let rafId = null;

  function cardWrap(card) { return card.closest(".card-wrap"); }
  function revealEl(wrap, side) { return wrap?.querySelector(`.swipe-reveal--${side}`); }

  function applySwipeFrame() {
    if (!g || g.mode !== "swipe") return;
    const dx = g.liveDx;
    g.el.style.transform = `translateX(${dx}px)`;
    const t = Math.min(Math.abs(dx) / SWIPE_THRESHOLD, 1);
    const wrap = cardWrap(g.el);
    const rightRev = revealEl(wrap, "right");
    const leftRev  = revealEl(wrap, "left");
    if (rightRev) rightRev.style.opacity = dx > 0 ? t : 0;
    if (leftRev)  leftRev.style.opacity  = dx < 0 ? t : 0;
    rafId = null;
  }

  function applyDragFrame() {
    if (!g || g.mode !== "drag") return;
    g.el.style.transform = `translateY(${g.liveDy}px)`;
    rafId = null;
  }

  function snapBack(card) {
    card.style.transition = "transform 0.25s cubic-bezier(0.25,1,0.5,1)";
    card.style.transform = "";
    const wrap = cardWrap(card);
    [revealEl(wrap, "right"), revealEl(wrap, "left")].forEach((r) => {
      if (r) r.style.opacity = 0;
    });
    card.addEventListener("transitionend", () => { card.style.transition = ""; }, { once: true });
  }

  function flyOff(card, dir) {
    const W = window.innerWidth;
    card.style.transition = "transform 0.28s cubic-bezier(0.4,0,1,1)";
    card.style.transform = `translateX(${dir > 0 ? W : -W}px)`;
  }

  listEl.addEventListener("pointerdown", (e) => {
    const card = e.target.closest(".card");
    if (!card || e.target.closest("button") || e.target.closest("input")) return;
    g = {
      id: card.dataset.id,
      el: card,
      startX: e.clientX,
      startY: e.clientY,
      liveDx: 0,
      liveDy: 0,
      moved: false,
      mode: null,
      timer: setTimeout(() => {
        if (g && !g.moved) {
          g.mode = "drag";
          card.classList.add("card--dragging");
          card.style.willChange = "transform";
          navigator.vibrate?.(12);
        }
      }, LONG_PRESS_MS),
    };
    card.setPointerCapture(e.pointerId);
  });

  listEl.addEventListener("pointermove", (e) => {
    if (!g) return;
    const dx = e.clientX - g.startX;
    const dy = e.clientY - g.startY;
    if (!g.moved && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
      g.moved = true;
      clearTimeout(g.timer);
      if (g.mode !== "drag") {
        g.mode = Math.abs(dx) > Math.abs(dy) ? "swipe" : "scroll";
        if (g.mode === "swipe") g.el.style.willChange = "transform";
      }
    }
    if (g.mode === "swipe") {
      e.preventDefault();
      g.liveDx = dx;
      if (!rafId) rafId = requestAnimationFrame(applySwipeFrame);
    } else if (g.mode === "drag") {
      e.preventDefault();
      g.liveDy = dy;
      if (!rafId) rafId = requestAnimationFrame(applyDragFrame);
    }
  });

  listEl.addEventListener("pointerup", async (e) => {
    if (!g) return;
    const { id, el, startX, startY, mode, moved } = g;
    clearTimeout(g.timer);
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    el.style.willChange = "";
    el.classList.remove("card--dragging");

    if (mode === "swipe" && Math.abs(dx) >= SWIPE_THRESHOLD) {
      flyOff(el, dx);
      el.addEventListener("transitionend", async () => {
        if (dx > 0) {
          await queueMutation({ id: generateId(), type: "complete-node", nodeId: id });
        } else {
          const node = nodeById(id);
          const next = node ? ((node.importance ?? 0) % 5) + 1 : 1;
          await queueMutation({ id: generateId(), type: "set-importance", nodeId: id, importance: next });
        }
      }, { once: true });
    } else if (mode === "swipe") {
      snapBack(el);
    } else if (mode === "drag" && Math.abs(dy) > 10) {
      el.style.transform = "";
      const cardH = el.offsetHeight + 12;
      const steps = Math.round(dy / cardH);
      if (steps !== 0) {
        const action = steps > 0 ? "move-node-down" : "move-node-up";
        for (let i = 0; i < Math.abs(steps); i++) {
          await queueMutation({ id: generateId(), type: action, nodeId: id });
        }
      }
    } else if (mode === "drag") {
      el.style.transform = "";
    } else if (!moved) {
      if (!e.target.closest("button") && !e.target.closest("input") && !e.target.closest(".card-detail-panel")) {
        const node = nodeById(id);
        if (node) {
          state.focusStack = [...pathNodes().map((n) => n.id), id];
          await persistAndRender();
        }
      }
    }
    g = null;
  });

  listEl.addEventListener("pointercancel", () => {
    if (!g) return;
    clearTimeout(g.timer);
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    snapBack(g.el);
    g.el.style.willChange = "";
    g.el.classList.remove("card--dragging");
    g = null;
  });
}

function startRename(id, titleEl) {
  if (titleEl.querySelector("input")) return;
  const node = nodeById(id);
  if (!node) return;
  const orig = node.title;
  const input = document.createElement("input");
  input.className = "rename-input";
  input.value = orig;
  titleEl.textContent = "";
  titleEl.appendChild(input);
  input.focus();
  input.select();
  let committed = false;
  async function commit() {
    if (committed) return;
    committed = true;
    const title = input.value.trim();
    if (title && title !== orig) {
      await queueMutation({ id: generateId(), type: "rename-node", nodeId: id, title });
    } else {
      render();
    }
  }
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    if (e.key === "Escape") { committed = true; render(); }
  });
  input.addEventListener("blur", commit);
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
    state.composerMode === "sibling"
      ? focus?.parentId
        ? `Sibling beside ${focus.title}`
        : "Another root goal"
      : focus
        ? `${childType(focus.type)} under ${focus.title}`
        : "A new root goal";
  els.composerInput.placeholder = target;
}

function openComposer() {
  els.composer.classList.remove("composer--collapsed");
  els.composer.classList.add("composer--open");
  els.composerInput.focus();
}

function closeComposer() {
  els.composer.classList.add("composer--collapsed");
  els.composer.classList.remove("composer--open");
  els.composerInput.value = "";
  composerPlaceholder();
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

const TYPE_COLORS = { goal: "#34d399", idea: "#60a5fa", step: "#c084fc", task: "#f87171", free: "#94a3b8" };

function renderDepthBackground() {
  const bg = document.getElementById("depth-bg");
  if (!bg) return;
  const path = pathNodes();
  const existing = bg.querySelectorAll(".depth-layer");
  // reuse or create layers
  path.forEach((node, i) => {
    let el = existing[i];
    if (!el) {
      el = document.createElement("div");
      el.className = "depth-layer";
      bg.appendChild(el);
    }
    el.dataset.depth = i;
    el.style.background = TYPE_COLORS[node.type] || TYPE_COLORS.free;
    requestAnimationFrame(() => el.classList.add("visible"));
  });
  // remove extra layers
  for (let i = path.length; i < existing.length; i++) {
    existing[i].classList.remove("visible");
    existing[i].addEventListener("transitionend", (e) => e.target.remove(), { once: true });
  }
}

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
  renderFocusCard();
  renderList();
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
    type: state.composerMode === "sibling" ? "add-sibling" : "add-child",
    parentId: currentFocusId(),
    siblingId: currentFocusId(),
  };
  closeComposer();
  await queueMutation(mutation);
});

els.syncButton.addEventListener("click", syncIfPossible);

els.navValues.addEventListener("click", () => {
  state.route = "values";
  render();
});

els.valuesBack.addEventListener("click", () => {
  state.route = "main";
  render();
});
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
els.composerFab.addEventListener("click", () => openComposer());

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && els.composer.classList.contains("composer--open")) {
    closeComposer();
  }
});

document.addEventListener("pointerdown", (e) => {
  if (
    els.composer.classList.contains("composer--open") &&
    !els.composer.contains(e.target) &&
    e.target !== els.composerFab
  ) {
    closeComposer();
  }
});

els.composerModeToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".mode-btn[data-mode]");
  if (!btn) return;
  state.composerMode = btn.dataset.mode;
  els.composerModeToggle.querySelectorAll(".mode-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === state.composerMode);
  });
  composerPlaceholder();
});

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
