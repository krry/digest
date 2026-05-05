#!/usr/bin/env bash
# gist add — append a node to the canonical digest store
# Usage: add.sh <type> <parentId|null> <title>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHONPATH="$ROOT_DIR" python3 -m digest.cli add "$1" "$2" "$3"
