# AGENTS.md

## Purpose

This project is a small personal GIST todo app:

- Python Textual TUI for interactive editing and navigation
- JSON backend stored in local files
- Small shell scripts for common actions and skill integration

The design is intentionally lightweight. Preserve that unless asked otherwise.

## Project Shape

- `bin/gist-tui`: main Python TUI app
- `gist-tui.tcss`: Textual styles for the TUI
- `bin/show.sh`: render the goal tree from JSON
- `bin/add.sh`: append a node to `goals.json`
- `bin/done.sh`: fuzzy-match and complete a node
- `bin/write-values.sh`: overwrite `values.json` from stdin JSON
- `bin/checkin-status.sh`: check monthly check-in throttle and print context
- `goals.json`: primary node store
- `values.json`: values store
- `checkins.json`: optional local check-in history file
- `*.json.example`: committed blank datastore templates

## Data Model

`goals.json` uses:

```json
{
  "version": 1,
  "nodes": []
}
```

Each node currently looks like:

```json
{
  "id": "abc123",
  "type": "goal | idea | step | task | free",
  "title": "string",
  "status": "active | completed | archived",
  "parentId": null,
  "createdAt": "UTC ISO-8601",
  "completedAt": null
}
```

Hierarchy convention:

- `goal -> idea -> step -> task -> free`

## Runtime Conventions

- Python is used only where it buys clarity; keep it small and direct.
- Shell scripts use `set -euo pipefail`.
- `jq` is used for JSON reads in shell.
- JSON writes are done with inline Python in shell scripts and directly in the TUI app.
- Timestamps are UTC ISO-8601 with a trailing `Z`.
- Naming is straightforward: snake_case, small helpers, minimal abstraction.

## TUI Notes

The TUI is a single-file Textual app with:

- Vim-style movement bindings
- Modal text input for add/rename
- In-memory undo stack
- Rebuild-based tree refresh after mutations
- Archived items hidden from the TUI tree

When editing the TUI, keep the interaction model fast and obvious. Avoid over-engineering.

## Skills Integration

Canonical skill docs now live in this repo:

- `skills/digest-gist/gist-show/SKILL.md`
- `skills/digest-gist/gist-add/SKILL.md`
- `skills/digest-gist/gist-done/SKILL.md`
- `skills/digest-gist/gist-checkin/SKILL.md`
- `skills/digest-gist/gist-onboard/SKILL.md`

External Codex skill paths under `/Users/kerry/.codex/skills/digest-gist/` should be symlinks pointing back to these repo files.

External Claude skill paths under `/Users/kerry/.claude/skills/` for `gist-show`, `gist-add`, `gist-done`, `gist-checkin`, and `gist-onboard` should also be symlinks pointing back to these same repo files.

Those skills assume the local scripts in `bin/` remain stable. If you change script behavior or output, update the matching skill docs in this repo too.

## Bootstrap

- Run `./bin/init.sh` after cloning to create local datastore files from committed `.example` templates.
- Live data files (`goals.json`, `values.json`, `checkins.json`) are ignored and should not be committed.
- Scripts and the TUI should still handle missing files gracefully, but `bin/init.sh` is the primary setup path.

## Commands

Use these when working on the project:

- `./bin/gist-tui`
- `./bin/init.sh`
- `./bin/show.sh`
- `./bin/show.sh all`
- `./bin/add.sh <type> <parentId|null> "<title>"`
- `./bin/done.sh <search terms>`
- `./bin/checkin-status.sh [force]`
- `echo '[{"phrase":"...","pinnedMoment":"..."}]' | ./bin/write-values.sh`
- `python3 -m py_compile bin/gist-tui`

## Change Guidelines

- Keep the project local-first and file-backed.
- Prefer small, legible edits over new architecture.
- Do not introduce a database, packaging layer, or framework sprawl unless explicitly requested.
- Be careful with live JSON files in the repo root; they are user data, not fixtures.
- Do not commit live JSON data; commit only the `.example` templates.
- If you change storage shape, update all readers/writers together.
- If you change script UX or output, verify the related skill still makes sense.

## Verification

There is no formal test suite yet. After changes:

- run `python3 -m py_compile bin/gist-tui` if Python changed
- run the affected shell script directly if shell changed
- launch `./bin/gist-tui` for manual verification if TUI behavior changed

## Caveats

- Root JSON files appear to be live data, so avoid casual edits during code changes.
