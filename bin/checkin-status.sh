#!/usr/bin/env bash
# gist checkin-status — check throttle and read context for check-in
# Prints: RECENT: <date>  OR  READY followed by values+goals context
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHONPATH="$ROOT_DIR" python3 -m digest.cli checkin-status "${1:-}"
