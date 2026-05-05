---
name: gist-checkin
description: Use when Chef wants a monthly drift check-in comparing active goals against stated values. Pass "force" to override the 20-day throttle.
---

# GIST Check-In

If the repo was just cloned or local datastore files are missing, run:

```bash
~/gist/bin/init.sh
```

## Steps

### 1. Check throttle and load context

```bash
~/gist/bin/checkin-status.sh [force]
```

- **`RECENT: <date>`** → say: *"Check-in was recent (<date>). Use `/gist-checkin force` to override."* Stop.
- **`READY\n...`** → read the values and active goals that follow. Proceed.

### 2. Ask one question

Don't summarize what you read. Ask one specific question surfacing the most interesting tension between what's active and what matters. Wait for the answer.

### 3. Follow the thread

Name what you hear. If action is needed, say it clearly:
- **retire_value** — might not be theirs anymore
- **demote_goal** — ran its course
- **pivot_goal** — what would the reframed version look like?
- **schedule_step** — smallest next move?
- **recommit** — still theirs, no change

### 4. Write the record

```bash
~/gist/bin/log-checkin.sh \
  --question "<the question you asked>" \
  --response "<one-sentence summary>" \
  --adjustment "<adjustment key>"
```

### 5. Close

> Check-in logged. See you next month.
