"""
Pytest configuration for the CSA-ACI backend.

Makes both the `csa_aci` package (vendored under csa_aci_fixed/src) and the
backend `app` package importable without installation, and supplies safe
default env vars so importing `app.main` does not require a live DB/Redis.
"""

import os
import sys
from pathlib import Path

# repo root = .../vaibhav  (tests -> backend -> vaibhav)
ROOT = Path(__file__).resolve().parents[2]

# Make the csa_aci package importable (same path Docker sets via PYTHONPATH).
sys.path.insert(0, str(ROOT / "csa_aci_fixed" / "src"))
# Make the backend `app` package importable.
sys.path.insert(0, str(ROOT / "backend"))

# Safe defaults so `app.core.database` / `app.core.security` import cleanly.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
