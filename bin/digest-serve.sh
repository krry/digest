#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec PYTHONPATH="$ROOT" python3 -m digest.api --host 127.0.0.1 --port 8787 --no-next-free
