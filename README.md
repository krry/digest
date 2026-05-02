# digest-gist

Small personal GIST todo app with a Python Textual TUI and JSON datastore.

## Setup

```bash
./bin/init.sh
```

That creates local `goals.json`, `values.json`, and `checkins.json` from committed `.example` templates if they do not already exist.

## Main commands

```bash
./bin/gist-tui
./bin/show.sh
./bin/show.sh all
./bin/add.sh <type> <parentId|null> "<title>"
./bin/done.sh <search terms>
./bin/checkin-status.sh [force]
echo '[{"phrase":"...","pinnedMoment":"..."}]' | ./bin/write-values.sh
```
