#!/usr/bin/env bash
# Start TitanAI backend in development mode.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Creating virtual environment..."
  python3.11 -m venv .venv
fi

source .venv/bin/activate

pip install -q -r requirements.txt

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Starting TitanAI backend on http://localhost:8000"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
