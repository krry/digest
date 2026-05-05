#!/usr/bin/env bash
# gist log-checkin — append a check-in record to the canonical digest store
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHONPATH="$ROOT_DIR" python3 -m digest.cli log-checkin "$@"
