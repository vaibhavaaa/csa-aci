"""
Google Cluster Trace loader.

Supports two real formats and normalises both to a CPU-utilisation series that
mapping.py turns into latency via the M/M/1 approximation:

  * 2019 Borg traces (BigQuery export): CSV/CSV.GZ WITH a header row; we pick a
    named CPU column (see CPU_COLUMN_CANDIDATES).
  * 2011-2 traces (clusterdata-2011-2): HEADERLESS task_usage CSV.GZ with 20
    positional columns; mean CPU usage rate is column index 5 per the official
    schema. Download via data/README.md into data/raw/google/task_usage/.

Files are discovered recursively under data/raw/google/ so the natural
task_usage/ subdir layout works. Values > 1 are treated as fractional core
counts and normalised by their max into [0, 1].
"""
from __future__ import annotations

import glob
import gzip
from pathlib import Path
from typing import List, Tuple

from .mapping import series_to_latency

CPU_COLUMN_CANDIDATES = [
    "cpu_util",
    "average_usage.cpus",
    "CPU_rate",
    "cpu_rate",
    "cpu",
]

# Official 2011-2 task_usage schema (headerless, 20 cols). Index 5 = mean CPU
# usage rate. https://github.com/google/cluster-data ClusterData2011_2.md
_TASK_USAGE_2011_COLUMNS = [
    "start_time", "end_time", "job_id", "task_index", "machine_id",
    "cpu_rate", "canonical_mem", "assigned_mem", "unmapped_page_cache",
    "total_page_cache", "max_mem", "mean_disk_io_time", "mean_local_disk",
    "max_cpu_rate", "max_disk_io_time", "cpi", "mai", "sample_portion",
    "agg_type", "sampled_cpu_usage",
]

# Cap how much raw data we read — these traces are huge.
_MAX_FILES = 5
_MAX_ROWS_PER_FILE = 1_000_000


def _find_cpu_column(df) -> str:
    for c in CPU_COLUMN_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:                       # any column mentioning cpu
        if "cpu" in str(c).lower():
            return c
    raise ValueError(
        f"No CPU column found. First columns: {list(df.columns)[:10]}"
    )


def _looks_headerless(path) -> bool:
    """True if the first line is all-numeric (2011 trace has no header row)."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as fh:
        first = fh.readline().strip()
    if not first:
        return False
    fields = first.split(",")
    if len(fields) < 10:                        # headered files are narrower
        return False
    try:
        [float(x) for x in fields[:6] if x != ""]
        return True
    except ValueError:
        return False


def _resample_mean(arr, n: int) -> List[float]:
    import numpy as np

    arr = np.asarray(arr, dtype=float)
    if arr.size == n:
        return arr.tolist()
    edges = np.linspace(0, arr.size, n + 1).astype(int)
    return [
        float(arr[edges[i]:max(edges[i] + 1, edges[i + 1])].mean())
        for i in range(n)
    ]


def _load_2011_demand(files, n_steps: int):
    """Aggregate cluster CPU DEMAND over time from 2011 task_usage parts.

    Each row is one task's usage over a measurement window, so a single row's
    cpu_rate is meaningless as a cluster signal. We sum cpu_rate across all
    concurrent tasks per uniform time-bin to get total cluster CPU demand, which
    is the bursty load series the controllers arbitrate over. The trace-start
    timestamp is dropped: every pre-existing task reports its first measurement
    there, an artifact that would dwarf real load.
    """
    import numpy as np
    import pandas as pd

    ts, cpu = [], []
    for f in files[:_MAX_FILES]:
        df = pd.read_csv(
            f, header=None, names=_TASK_USAGE_2011_COLUMNS,
            usecols=[0, 5], nrows=_MAX_ROWS_PER_FILE,
        )
        ts.append(pd.to_numeric(df["start_time"], errors="coerce").to_numpy())
        cpu.append(pd.to_numeric(df["cpu_rate"], errors="coerce").to_numpy())
    t = np.concatenate(ts)
    c = np.concatenate(cpu)
    ok = np.isfinite(t) & np.isfinite(c)
    t, c = t[ok], c[ok]

    keep = t > t.min()                          # drop trace-start artifact
    t, c = t[keep], c[keep]
    if t.size == 0:
        raise ValueError("No task_usage rows after dropping trace-start window")

    edges = np.linspace(t.min(), t.max() + 1, n_steps + 1)
    idx = np.clip(np.digitize(t, edges) - 1, 0, n_steps - 1)
    demand = np.bincount(idx, weights=c, minlength=n_steps).astype(float)
    return demand


def to_latency_series(
    raw_dir,
    n_steps: int = 100,
    base_ms: float = 20.0,
) -> Tuple[List[float], dict]:
    """Load Google CPU utilisation and return (latencies, provenance)."""
    import numpy as np
    import pandas as pd

    raw_dir = Path(raw_dir)
    # Recursive so the task_usage/ subdir layout (2011 trace) is discovered.
    files = sorted(glob.glob(str(raw_dir / "**" / "*.csv"), recursive=True)) + \
        sorted(glob.glob(str(raw_dir / "**" / "*.csv.gz"), recursive=True))
    if not files:
        raise FileNotFoundError(f"No CSV files in {raw_dir}")

    if _looks_headerless(files[0]):             # 2011 task_usage
        util = np.asarray(_load_2011_demand(files, n_steps), dtype=float)
        col, signal = "cpu_rate", "summed cluster CPU demand per time-bin"
    else:                                        # 2019 headered export
        parts = []
        for f in files[:_MAX_FILES]:
            df = pd.read_csv(f, nrows=_MAX_ROWS_PER_FILE)
            c = _find_cpu_column(df)
            parts.append(pd.to_numeric(df[c], errors="coerce").dropna().to_numpy())
        util = np.asarray(_resample_mean(np.concatenate(parts), n_steps))
        col, signal = c, "per-instance CPU utilisation"

    if util.max() > 1.0:                        # demand / core counts -> [0,1]
        util = util / util.max()

    latencies = series_to_latency(util, base_ms=base_ms)

    provenance = {
        "dataset": "google",
        "source": "real",
        "files": [Path(f).name for f in files[:_MAX_FILES]],
        "cpu_column": col,
        "signal": signal,
        "base_ms": base_ms,
        "normalisation": "utilisation = demand / max(demand)",
        "mapping": "M/M/1: base_ms / (1 - rho)",
    }
    return latencies, provenance
