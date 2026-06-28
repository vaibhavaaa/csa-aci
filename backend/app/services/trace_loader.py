"""
Unified trace loader — bridges real production traces to the CCE experiments.

`load_trace(name, n_steps)` returns a latency sequence plus provenance:

  * If real raw files exist under data/raw/<name>/, they are parsed and used
    (source="real").
  * Otherwise, when allow_synthetic=True, a CLEARLY LABELLED synthetic fallback
    is generated (source="synthetic_fallback") so the whole pipeline is runnable
    before the multi-GB datasets are downloaded.

IMPORTANT: results are only paper-valid when source == "real". The fallback
exists for development/testing and always carries a loud warning in its
provenance so the dashboard and paper can never mistake it for real data.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# repo root: services -> app -> backend -> root
_ROOT = Path(__file__).resolve().parents[3]
_DATA = _ROOT / "data"
_RAW = _DATA / "raw"
_PROCESSED = _DATA / "processed"

# Make the `data.loaders` package importable (data/ lives at the repo root).
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DATASETS = {
    "google": {
        "label": "Google Cluster Trace 2019",
        "description": "Borg CPU utilisation mapped to latency via M/M/1.",
        "raw_subdir": "google",
    },
    "wikipedia": {
        "label": "Wikipedia Pageviews",
        "description": "Hourly request rate mapped to latency; flash crowds spike.",
        "raw_subdir": "wikipedia",
    },
    "measured": {
        "label": "Measured HTTP Latency (microbenchmark)",
        "description": "Real wall-clock latency of a live HTTP service under induced load — NO M/M/1 model.",
        "raw_subdir": "measured",
    },
}


def _has_real_data(raw_dir: Path) -> bool:
    if not raw_dir.exists():
        return False
    return any(
        p.is_file() and p.name != ".gitkeep" for p in raw_dir.iterdir()
    )


def list_datasets() -> List[dict]:
    """Report available datasets and whether real data is present on disk."""
    out = []
    for name, meta in DATASETS.items():
        out.append({
            "name": name,
            "label": meta["label"],
            "description": meta["description"],
            "real_data_available": _has_real_data(_RAW / meta["raw_subdir"]),
        })
    return out


def load_trace(
    name: str,
    n_steps: int = 100,
    base_ms: float = 20.0,
    allow_synthetic: bool = True,
) -> dict:
    """Return {name, label, source, n_steps, latency, provenance}."""
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset '{name}'. Options: {list(DATASETS)}")

    meta = DATASETS[name]
    raw_dir = _RAW / meta["raw_subdir"]

    if _has_real_data(raw_dir):
        try:
            latencies, prov = _load_real(name, raw_dir, n_steps, base_ms)
            _cache(name, n_steps, latencies, prov)
            return {
                "name": name, "label": meta["label"], "source": "real",
                "n_steps": len(latencies), "latency": latencies, "provenance": prov,
            }
        except Exception as e:  # noqa: BLE001 — degrade gracefully, log loudly
            logger.warning("Real load failed for '%s' (%s); falling back.", name, e)
            if not allow_synthetic:
                raise

    if not allow_synthetic:
        raise FileNotFoundError(
            f"No real data for '{name}' in {raw_dir} and synthetic disabled."
        )

    latencies, prov = _synthetic_fallback(name, n_steps, base_ms)
    logger.warning(
        "Using SYNTHETIC FALLBACK for '%s' — results are NOT paper-valid.", name
    )
    return {
        "name": name, "label": meta["label"], "source": "synthetic_fallback",
        "n_steps": len(latencies), "latency": latencies, "provenance": prov,
    }


def _load_real(name, raw_dir, n_steps, base_ms) -> Tuple[List[float], dict]:
    from data.loaders import google_cluster, wikipedia, measured

    if name == "google":
        return google_cluster.to_latency_series(raw_dir, n_steps, base_ms)
    if name == "wikipedia":
        return wikipedia.to_latency_series(raw_dir, n_steps, base_ms)
    if name == "measured":
        return measured.to_latency_series(raw_dir, n_steps, base_ms)
    raise ValueError(name)


def _synthetic_fallback(name, n_steps, base_ms) -> Tuple[List[float], dict]:
    import numpy as np
    from data.loaders.mapping import series_to_latency

    rng = np.random.default_rng(42)
    if name == "google":
        # bursty utilisation: moderate base + occasional saturation bursts
        base = rng.beta(2, 5, n_steps)
        bursts = (rng.random(n_steps) < 0.08) * rng.uniform(0.4, 0.7, n_steps)
        util = np.clip(base + bursts, 0.0, 0.98)
    else:  # wikipedia: diurnal cycle + a flash crowd
        t = np.linspace(0, 4 * np.pi, n_steps)
        diurnal = 0.35 + 0.15 * np.sin(t)
        flash = np.zeros(n_steps)
        s = n_steps // 2
        flash[s:s + 5] = 0.5
        util = np.clip(diurnal + flash + rng.normal(0, 0.05, n_steps), 0.0, 0.98)

    latencies = series_to_latency(util, base_ms=base_ms)
    provenance = {
        "dataset": name,
        "source": "synthetic_fallback",
        "seed": 42,
        "base_ms": base_ms,
        "mapping": "M/M/1: base_ms / (1 - rho)",
        "warning": (
            "SYNTHETIC FALLBACK — not real data. Drop real files into "
            f"data/raw/{name}/ for paper-valid results."
        ),
    }
    return latencies, provenance


def _cache(name, n_steps, latencies, prov) -> None:
    try:
        _PROCESSED.mkdir(parents=True, exist_ok=True)
        (_PROCESSED / f"{name}_{n_steps}.json").write_text(
            json.dumps({"latency": latencies, "provenance": prov}, indent=2)
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Cache write failed: %s", e)
