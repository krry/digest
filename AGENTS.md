# AGENTS.md

## Purpose

This project is a small personal GIST todo app:

- Python Textual TUI for interactive editing and navigation
- SQLite canonical store with mirrored JSON export files
- Small shell scripts for common actions and skill integration

The design is intentionally lightweight. Preserve that unless asked otherwise.

## Project Shape

- `bin/gist-tui`: main Python TUI app
- `bin/digest-api.sh`: local private API + PWA server
- `gist-tui.tcss`: Textual styles for the TUI
- `bin/show.sh`: render the goal tree from JSON
- `bin/add.sh`: append a node to `goals.json`
- `bin/done.sh`: fuzzy-match and complete a node
- `bin/write-values.sh`: overwrite `values.json` from stdin JSON
- `bin/checkin-status.sh`: check monthly check-in throttle and print context
- `bin/log-checkin.sh`: append a check-in record
- `goals.json`: primary node store
- `values.json`: values store
- `checkins.json`: optional local check-in history file
- `digest.db`: canonical local datastore
- `web/`: mobile-first PWA shell with IndexedDB cache and service worker
- `prefs.json`: user preferences (theme, view mode, sort, expanded nodes)
- `*.json.example`: committed blank datastore templates

## Data Model

Canonical storage lives in `digest.db`. JSON mirrors still use:

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
  "importance": null,
  "dueDate": null,
  "tags": [],
  "createdAt": "UTC ISO-8601",
  "completedAt": null
}
```

- `importance`: integer 1–5 or null (1 = lowest, 5 = highest)
- `dueDate`: ISO-8601 partial date — `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`
- `tags`: array of strings

Hierarchy convention:

- `goal -> idea -> step -> task -> free`

## Runtime Conventions

- Python is used only where it buys clarity; keep it small and direct.
- Shell scripts use `set -euo pipefail`.
- `jq` is used for JSON reads in shell.
- shared datastore behavior lives in `digest/`
- JSON mirrors are export/compatibility artifacts, not the source of truth
- Timestamps are UTC ISO-8601 with a trailing `Z`.
- Naming is straightforward: snake_case, small helpers, minimal abstraction.

## TUI Notes

The TUI is a single-file Textual app with:

- Two views: **column browser** (default, Miller-columns style) and **tree view** (fully expanded by default)
- Vim-style movement bindings (`j`/`k`, `h`/`l` or arrows)
- Modal text input for add/rename/tags/due-date
- In-memory undo stack
- Rebuild-based tree refresh after mutations
- Archived items hidden from both views
- **Context panel** (toggle `c`): title/status, parent/metadata, last-action line
- **Sort**: cycle column sort with `s`; modes: manual, title, created, status, completed, importance, due; sort indicator shown in panel title
- **Importance**: cycle 1–5 with `i`; displayed as `!` glyphs
- **Cut/yank/paste**: `x` cuts, `y` yanks, `p` pastes; moved/duplicated nodes auto-retype to natural hierarchy type
- **Auto-retype**: moving a node (indent/unindent/paste) sets its `type` to the natural child type of the new parent (`goal→idea→step→task→free`)
- **Themes**: system light/dark responsive; separate defaults for each mode; chosen theme remembered in `prefs.json`
- **Space launcher** (`<space>`): modal to launch Claude skills from within the TUI
- **Ex-mode** (`:`): command line for aliases like `show`, `checkin`, `prefs`, `q`
- `prefs.json` persists: theme per mode, view mode, column sort per column, expanded node IDs

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
- `./bin/init.sh` also bootstraps `digest.db`.
- Live data files (`goals.json`, `values.json`, `checkins.json`) are ignored and should not be committed.
- `digest.db` is also ignored and should not be committed.
- Scripts and the TUI should still handle missing files gracefully, but `bin/init.sh` is the primary setup path.

## Commands

Use these when working on the project:

- `./bin/gist-tui`
- `./bin/digest-api.sh`
- `./bin/init.sh`
- `./bin/show.sh`
- `./bin/show.sh all`
- `./bin/add.sh <type> <parentId|null> "<title>"`
- `./bin/done.sh <search terms>`
- `./bin/checkin-status.sh [force]`
- `./bin/log-checkin.sh --question "..." --response "..." --adjustment "..." [--date YYYY-MM-DD]`
- `echo '[{"phrase":"...","pinnedMoment":"..."}]' | ./bin/write-values.sh`
- `PYTHONPATH=. python3 -m digest.cli export-json`
- `python3 -m py_compile bin/gist-tui`

## Change Guidelines

- Keep the project local-first and single-user.
- Prefer small, legible edits over new architecture.
- Be careful with `digest.db` and the live JSON mirrors in the repo root; they are user data, not fixtures.
- Do not commit live SQLite or JSON data; commit only the `.example` templates.
- If you change storage shape, update the shared core, scripts, and skill docs together.
- If you change script UX or output, verify the related skill still makes sense.

## Verification

There is no formal test suite yet. After changes:

- run `python3 -m py_compile bin/gist-tui` if Python changed
- run the affected shell script directly if shell changed
- launch `./bin/gist-tui` for manual verification if TUI behavior changed

## Caveats

- Root JSON files appear to be live data, so avoid casual edits during code changes.
