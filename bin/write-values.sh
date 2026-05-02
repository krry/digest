#!/usr/bin/env bash
# gist write-values — write values.json from JSON on stdin
# Usage: echo '[{"phrase":"...","pinnedMoment":"..."}]' | write-values.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALUES="$ROOT_DIR/values.json"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
INPUT=$(cat)

python3 - <<PYEOF
import json, sys

values = json.loads('''$INPUT''')
data = {
    "version": 1,
    "establishedAt": "$NOW",
    "values": values
}

with open("$VALUES", "w") as f:
    json.dump(data, f, indent=2)

print(f"Saved {len(values)} value(s) to $VALUES")
PYEOF
