"""
Wikipedia pageview trace loader.

Real data: hourly pageview counts from dumps.wikimedia.org. Download per
data/README.md into data/raw/wikipedia/. Each hourly file's total request count
becomes one timestep; the rate series is normalised to a utilisation
rho = rate / capacity and mapped to latency via M/M/1. Flash crowds drive
rho -> 1 (a latency spike), which exercises the CCE emergency-override path.

Accepted formats per file:
  * Wikimedia pageviews: whitespace-separated `domain page count bytes`
    (we sum the count column).
  * Plain: one numeric value per line (summed).
"""
from __future__ import annotations

import glob
from pathlib import Path
from typing import List, Tuple

from .mapping import series_to_latency

_MAX_ROWS_PER_FILE = 500_000


def _read_counts(files) -> "List[float]":
    import numpy as np
    import pandas as pd

    totals: List[float] = []
    for f in files:
        try:                                   # pageviews: count in 3rd column
            df = pd.read_csv(
                f, sep=r"\s+", header=None, usecols=[2], names=["c"],
                engine="python", on_bad_lines="skip", nrows=_MAX_ROWS_PER_FILE,
            )
            totals.append(float(pd.to_numeric(df["c"], errors="coerce").fillna(0).sum()))
        except Exception:
            try:                               # fallback: one number per line
                totals.append(float(np.loadtxt(f).sum()))
            except Exception:
                continue
    if not totals:
        raise ValueError("Could not parse any Wikipedia count files")
    return totals


def _resample_interp(arr, n: int):
    import numpy as np

    arr = np.asarray(arr, dtype=float)
    if arr.size == n:
        return arr
    xp = np.linspace(0.0, 1.0, arr.size)
    x = np.linspace(0.0, 1.0, n)
    return np.interp(x, xp, arr)


def to_latency_series(
    raw_dir,
    n_steps: int = 100,
    base_ms: float = 20.0,
    capacity_percentile: int = 90,
) -> Tuple[List[float], dict]:
    """Load Wikipedia pageview rate and return (latencies, provenance)."""
    import numpy as np

    raw_dir = Path(raw_dir)
    files = [f for f in sorted(glob.glob(str(raw_dir / "*"))) if Path(f).is_file()
             and not f.endswith(".gitkeep")]
    if not files:
        raise FileNotFoundError(f"No files in {raw_dir}")

    counts = _read_counts(files)
    rate = _resample_interp(counts, n_steps)

    # capacity = headroom above the p90 rate; normal load -> moderate rho,
    # flash crowds -> rho near 1 (saturation).
    cap = float(np.percentile(rate, capacity_percentile)) * 1.25 + 1e-9
    rho = np.clip(rate / cap, 0.0, 0.99)

    latencies = series_to_latency(rho, base_ms=base_ms)
    provenance = {
        "dataset": "wikipedia",
        "source": "real",
        "files": [Path(f).name for f in files[:5]],
        "capacity_percentile": capacity_percentile,
        "base_ms": base_ms,
        "mapping": "M/M/1 on rho = rate / capacity",
    }
    return latencies, provenance
