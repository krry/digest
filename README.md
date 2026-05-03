# digest-gist

A tiny personal goals-and-todos app.

It lives in the terminal, uses [Textual](https://textual.textualize.io/) for the TUI, and stores everything in local JSON files.

## Setup

```bash
./bin/init.sh
```

Creates local data files from committed examples and links the repo-owned GIST skills into `~/.codex/skills` and `~/.claude/skills`. Your actual data stays untracked.

## Use it

```bash
./bin/gist-tui        # open the interactive TUI
./bin/show.sh         # print the current tree
./bin/show.sh all     # include archived items
```

## TUI — key bindings

| Key | Action |
|-----|--------|
| `j` / `k` | move down / up |
| `h` / `l` | column left / right (column view) |
| `tab` | switch column / tree view |
| `a` | add child node |
| `A` | add sibling node |
| `r` | rename |
| `d` | mark done |
| `D` | archive |
| `x` | cut node |
| `y` | yank (copy) node |
| `p` | paste under selection |
| `>` | indent (reparent deeper) |
| `<` | unindent (reparent shallower) |
| `i` | cycle importance (1–5) |
| `u` | set due date (YYYY, YYYY-MM, or YYYY-MM-DD) |
| `T` | edit tags |
| `s` | cycle column sort |
| `f` | toggle filter (all / active only) |
| `c` | toggle context panel |
| `t` | toggle theme |
| `<space>` | launcher — open a Claude skill |
| `:` | ex-mode — type a command |
| `?` | help |
| `q` | quit |

## Node types

`goal → idea → step → task → free`

Nodes auto-retype when moved to a new position in the hierarchy.

## Node fields

| Field | Values |
|-------|--------|
| `type` | `goal \| idea \| step \| task \| free` |
| `status` | `active \| completed \| archived` |
| `importance` | 1–5 or null |
| `dueDate` | `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` |
| `tags` | list of strings |

## Launcher / ex-mode

`<space>` opens a modal with quick-launch shortcuts for Claude skills. `:` opens a command line. Available aliases: `show`, `checkin`, `onboard`, `prefs`, `q`.

## Preferences

`prefs.json` (untracked) stores your theme choices, last view mode, column sort, and which tree nodes were expanded. It's created automatically on first run.
