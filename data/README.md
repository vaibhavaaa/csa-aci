# CSA-ACI — Real Trace Data

This directory feeds **real production traces** into the CCE experiments. The raw
datasets are large and **not committed**; download them into `raw/<dataset>/`
and the loaders pick them up automatically.

## Provenance contract
`backend/app/services/trace_loader.py` always reports a `source` field:
- `"real"` — parsed from files in `raw/<dataset>/`.
- `"synthetic_fallback"` — generated because no real files were found. **Not
  paper-valid.** Used only so the pipeline runs before you download the data.

Experiments and the dashboard surface this field. **Only `source == "real"`
results may appear in the paper.**

## Current status (2026-06-11)
| Dataset | Status | What's on disk |
|---|---|---|
| Google Cluster 2019 | ✅ **real** | `raw/google/task_usage/part-00000-of-00500.csv.gz` (summed cluster CPU demand → M/M/1 latency) |
| Wikipedia Pageviews | ✅ **real** | `raw/wikipedia/projectviews-*` (24 hourly files) |
| Measured HTTP latency | ✅ **real (measured)** | `raw/measured/measured_latency.json` — wall-clock latency of a live service under induced load; **no M/M/1 model** |
| Azure VM traces | ⬜ optional 4th | not downloaded — see §4 below to enable |

**Three real traces** satisfy the paper's 2–3 real-trace requirement. Two
(Google, Wikipedia) are signal→latency via M/M/1; the **measured** trace is
genuine wall-clock latency (removes the "latency is modeled" threat for one
dataset). Reproduce with `scripts/fetch_traces.{sh,ps1}` (Google/Wikipedia) and
`scripts/collect_measured_latency.py` (measured).

## Layout
```
data/
├── raw/                 # downloaded datasets (gitignored, not committed)
│   ├── google/
│   └── wikipedia/
├── processed/           # cached latency series (auto-written)
└── loaders/             # parsers (google_cluster.py, wikipedia.py, mapping.py)
```

## Datasets

### 1. Google Cluster Trace 2019 (`raw/google/`)
- Source: https://github.com/google/cluster-data (ClusterData2019)
- Put one or more **instance-usage CSV** files (with a CPU-utilisation column)
  into `raw/google/`. Accepted column names: `cpu_util`, `average_usage.cpus`,
  `CPU_rate`, `cpu_rate`, `cpu` (values > 1 are treated as core counts and
  normalised). `.csv` and `.csv.gz` are both accepted.
- Mapping: CPU utilisation → latency via M/M/1 `R = base_ms / (1 - rho)`.

### 2. Wikipedia Pageviews (`raw/wikipedia/`)
- Source: https://dumps.wikimedia.org/other/pageviews/
- Put **hourly pageview files** into `raw/wikipedia/`. Each file's total request
  count becomes one timestep. Wikimedia format `domain page count bytes`
  (whitespace-separated) or one-number-per-line are both accepted.
- Mapping: request rate → `rho = rate / capacity` → latency via M/M/1. Flash
  crowds drive `rho → 1` (latency spike), exercising the CCE emergency override.

### 3. Measured HTTP Latency (`raw/measured/`)
- Source: collected locally by `scripts/collect_measured_latency.py`, which load-
  tests the running backend and records **real per-request wall-clock latency
  (ms)** under periodic concurrency bursts (sustained-load episodes + short
  transient spikes).
- **No M/M/1 mapping** — the measured milliseconds are used as-is (loader:
  `data/loaders/measured.py`). This is the trace that removes the "latency is
  modeled" threat to validity for one dataset.
- Reproduce: `python scripts/collect_measured_latency.py` (writes
  `raw/measured/measured_latency.json`; absolute latencies are machine-dependent,
  so the saved series is the reproducible artifact — provenance records the host
  conditions and p50/p95/max).

### 4. Azure VM Traces (optional 4th — `raw/azure/`)
- Source: https://github.com/Azure/AzurePublicDataset (VM CPU readings, 5-min bins)
- Recommended additional dataset for breadth (a different workload shape: per-VM
  CPU with strong diurnality). Put the per-VM CPU-utilisation CSV(s) into `raw/azure/`.
- Enabling it requires a `data/loaders/azure.py` parser mirroring `google_cluster.py`
  (same `cpu → rho → M/M/1` mapping) and an `"azure"` entry in `DATASETS`. Until
  then `load_trace("azure")` is unavailable and the eval runs on the three datasets above.

## Reproducible download
`scripts/fetch_traces.sh` (bash) and `scripts/fetch_traces.ps1` (Windows) fetch
Wikipedia automatically and print the exact `gsutil`/Azure commands for the larger
datasets (which need their respective CLIs / accept terms).
`scripts/collect_measured_latency.py` collects the measured trace.

## Usage
```python
from app.services.trace_loader import load_trace, list_datasets

list_datasets()                 # which datasets have real data on disk
res = load_trace("google", n_steps=100)
print(res["source"], res["n_steps"], res["latency"][:5])
```
The resulting `latency` list is fed to `TelemetrySnapshot` exactly like the
synthetic simulation steps, so every controller (Threshold, Hysteresis, EMA,
PID, CCE) runs on the identical real sequence.
