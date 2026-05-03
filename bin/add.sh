#!/usr/bin/env bash
# gist add — append a node to goals.json
# Usage: add.sh <type> <parentId|null> <title>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GOALS="$ROOT_DIR/goals.json"
TYPE="$1"
PARENT_ID="$2"   # literal "null" or an id string
TITLE="$3"

# generate 6-char alphanumeric id
ID=$(python3 -c "import secrets; print(secrets.token_hex(3))")
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# init file if missing
if [[ ! -f "$GOALS" ]]; then
  cp "$ROOT_DIR/goals.json.example" "$GOALS"
fi

python3 - <<PYEOF
import json, sys

path = "$GOALS"
with open(path) as f:
    data = json.load(f)

node = {
    "id": "$ID",
    "type": "$TYPE",
    "title": "$TITLE",
    "status": "active",
    "parentId": None if "$PARENT_ID" == "null" else "$PARENT_ID",
    "importance": None,
    "dueDate": None,
    "tags": [],
    "createdAt": "$NOW",
    "completedAt": None,
}

data["nodes"].append(node)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(f"$ID")
PYEOF
