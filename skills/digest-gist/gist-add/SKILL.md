---
name: gist-add
description: Use when Chef wants to add a goal, idea, step, task, or free node to their GIST tree.
---

# GIST Add

If the repo was just cloned or local datastore files are missing, run:

```bash
~/gist/bin/init.sh
```

## Steps

### 1. Parse intent

Determine from Chef's message:
- **type**: `goal | idea | step | task | free` — infer from context or explicit label
- **title**: text of the node
- **parentId**: required for non-goal types

If type is ambiguous and no parent context, ask: *"Is this a goal, or does it belong under something?"*

### 2. Resolve parent if needed

```bash
~/gist/bin/show.sh
```

Fuzzy-match Chef's description against the tree. If multiple candidates, ask which.

### 3. Write the node

```bash
~/gist/bin/add.sh <type> <parentId|null> "<title>"
```

Script writes to the canonical SQLite store and prints the new node's ID.

### 4. Confirm

- Root: `Added: G  <title>`
- Child: `Added under "<parent title>": <badge>  <title>`
