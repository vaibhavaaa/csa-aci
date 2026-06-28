#!/usr/bin/env bash
# cleanup.sh
# Run from the repo root (where vaibhav/ lives) to apply all cleanup changes.
# Safe to run multiple times — deletes only files that have no live imports.

set -e

BACKEND="vaibhav/backend/app"

echo "=== CSA-ACI Cleanup Script ==="

# ── 1. Delete orphaned service files ──────────────────────────────────────────
echo "[1/3] Removing orphaned files..."

rm -f "$BACKEND/services/cognitive_engine.py"
echo "  ✓ deleted services/cognitive_engine.py"

rm -f "$BACKEND/services/orchestrator.py"
echo "  ✓ deleted services/orchestrator.py"

rm -f "$BACKEND/services/aws_executor.py"
echo "  ✓ deleted services/aws_executor.py  (was empty)"

# ── 2. Remove stale __pycache__ for deleted files ─────────────────────────────
echo "[2/3] Cleaning __pycache__ for removed modules..."

rm -f "$BACKEND/services/__pycache__/cognitive_engine.cpython-311.pyc"
rm -f "$BACKEND/services/__pycache__/cognitive_engine.cpython-313.pyc"
rm -f "$BACKEND/services/__pycache__/orchestrator.cpython-311.pyc"
rm -f "$BACKEND/services/__pycache__/orchestrator.cpython-313.pyc"
echo "  ✓ stale bytecode removed"

# ── 3. Verify nothing imports the deleted modules ─────────────────────────────
echo "[3/3] Verifying no live imports remain..."

if grep -r "from app.services.cognitive_engine" "$BACKEND" 2>/dev/null; then
  echo "  ✗ WARN: something still imports cognitive_engine — check above"
  exit 1
fi

if grep -r "from app.services.orchestrator" "$BACKEND" 2>/dev/null; then
  echo "  ✗ WARN: something still imports orchestrator — check above"
  exit 1
fi

echo "  ✓ no stray imports found"
echo ""
echo "=== Cleanup complete ==="
echo ""
echo "Next: copy the updated supervisor_engine.py from this PR into"
echo "  $BACKEND/services/supervisor_engine.py"