# digest-gist

A tiny personal goals-and-todos app.

It lives in the terminal, uses [Textual](https://textual.textualize.io/) for the TUI, and stores everything in local JSON files.

## Setup

Run:

```bash
./bin/init.sh
```

That creates your local data files from the committed examples. Your actual data stays untracked.

## Use it

- `./bin/gist-tui` opens the interactive app.
- `./bin/show.sh` prints the current tree.
- `./bin/show.sh all` includes archived items.

Everything else in `bin/` is there to support the skills and small scriptable actions.
