#!/usr/bin/env bash
# ==============================================================================
# IceStream Week 1 Checkpoint Validation Shell Runner
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${PROJECT_ROOT}"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/week1_checkpoint.py
else
    python3 scripts/week1_checkpoint.py
fi
