#!/usr/bin/env bash
# gist done — fuzzy-match an active node by title and mark it complete
# Usage: done.sh <search term>
# Exit 0 + prints "DONE: <title>" on success
# Exit 0 + prints "MATCHES:\n..." when ambiguous (Claude picks)
# Exit 1 + prints "NONE" when nothing found
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GOALS="$ROOT_DIR/goals.json"
QUERY="${*}"

if [[ ! -f "$GOALS" ]]; then
  echo "NONE"
  exit 1
fi

# find active nodes whose title contains the query (case-insensitive)
mapfile -t matches < <(
  jq -r --arg q "$QUERY" \
    '.nodes[] | select(.status == "active") | select(.title | ascii_downcase | contains($q | ascii_downcase)) | "\(.id)\t\(.type)\t\(.title)"' \
    "$GOALS"
)

if [[ ${#matches[@]} -eq 0 ]]; then
  echo "NONE"
  exit 1
fi

if [[ ${#matches[@]} -gt 1 ]]; then
  echo "MATCHES:"
  for m in "${matches[@]}"; do
    id=$(echo "$m" | cut -f1)
    type=$(echo "$m" | cut -f2)
    title=$(echo "$m" | cut -f3)
    badge=$(case "$type" in goal) echo G;; idea) echo I;; step) echo S;; task) echo T;; *) echo ·;; esac)
    echo "  [$id] $badge  $title"
  done
  exit 0
fi

# single match — mark complete
id=$(echo "${matches[0]}" | cut -f1)
title=$(echo "${matches[0]}" | cut -f3)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 - <<PYEOF
import json

path = "$GOALS"
with open(path) as f:
    data = json.load(f)

for node in data["nodes"]:
    if node["id"] == "$id":
        node["status"] = "completed"
        node["completedAt"] = "$NOW"
        break

with open(path, "w") as f:
    json.dump(data, f, indent=2)
PYEOF

echo "DONE: $title"
