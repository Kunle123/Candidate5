#!/bin/bash
# Always run Alembic from the Ark service directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/apps/arc/arc_service" || exit 1
alembic "$@"
