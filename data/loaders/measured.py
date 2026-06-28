"""
Measured-latency loader.

Unlike google_cluster / wikipedia (which map a CPU or request-rate signal to
latency via an M/M/1 model), this dataset is ALREADY latency: real wall-clock
HTTP response times collected by scripts/collect_measured_latency.py. There is
therefore NO mapping — the measured milliseconds are returned as-is. This is the
trace that removes the "latency is modeled" threat to validity for one dataset.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple


def to_latency_series(raw_dir, n_steps: int, base_ms: float) -> Tuple[List[float], dict]:
    raw_dir = Path(raw_dir)
    files = sorted(p for p in raw_dir.iterdir() if p.suffix == ".json")
    if not files:
        raise FileNotFoundError(
            f"No measured-latency JSON in {raw_dir}. Run scripts/collect_measured_latency.py."
        )

    data = json.loads(files[0].read_text())
    latencies = [float(x) for x in data.get("latency", [])]
    if not latencies:
        raise ValueError(f"{files[0].name} has no 'latency' array.")

    series = latencies[:n_steps] if len(latencies) >= n_steps else latencies

    provenance = {
        "dataset": "measured",
        "source": "real",
        "measured": True,
        "file": files[0].name,
        "mapping": "NONE — measured wall-clock HTTP latency (ms); no M/M/1 model",
        # carry through collection details (url, concurrency, percentiles, timestamp)
        **{k: v for k, v in data.get("provenance", {}).items()
           if k not in ("dataset", "source", "measured")},
    }
    return series, provenance
