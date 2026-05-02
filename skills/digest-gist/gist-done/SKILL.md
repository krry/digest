---
name: gist-done
description: Use when Chef wants to mark a goal, idea, step, or task as complete.
---

# GIST Done

If the repo was just cloned or local datastore files are missing, run:

```bash
~/gist/bin/init.sh
```

```bash
~/gist/bin/done.sh <search terms>
```

Handle output:
- **`DONE: <title>`** → print `✓ <title>`
- **`MATCHES:\n...`** → show list, ask which, re-run with exact title
- **`NONE`** → say nothing matched, run `~/gist/bin/show.sh` so Chef can see active nodes
