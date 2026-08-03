#!/usr/bin/env bash
# Run the test suite.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -d ".venv" ]]; then
  source .venv/bin/activate
fi

exec pytest tests/ -v "$@"
