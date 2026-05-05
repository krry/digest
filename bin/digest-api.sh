#!/usr/bin/env bash
# digest api — serve the private web client and JSON API
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHONPATH="$ROOT_DIR" python3 -m digest.api "$@"
