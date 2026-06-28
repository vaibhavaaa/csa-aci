#!/usr/bin/env python3
"""
Collect a MEASURED latency trace — real wall-clock HTTP response times of the
live backend under induced concurrency. Unlike the Google/Wikipedia traces
(CPU/request-rate mapped to latency via an M/M/1 model), this is *measured*
latency: real jitter, real tail spikes from contention, no model.

Output: data/raw/measured/measured_latency.json  ({latency: [...ms], provenance})
which trace_loader picks up as source=="real".

Usage:  python scripts/collect_measured_latency.py
Env:    MEASURE_URL (default http://localhost:8000/openapi.json)
        MEASURE_N (default 360)   MEASURE_BURST (default 48 concurrent)
"""
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = os.environ.get("MEASURE_URL", "http://localhost:8000/openapi.json")
N = int(os.environ.get("MEASURE_N", "360"))
BURST = int(os.environ.get("MEASURE_BURST", "160"))  # enough to push sustained latency clearly >100ms
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "measured"


def _get():
    try:
        with urllib.request.urlopen(URL, timeout=15) as r:
            r.read()
    except Exception:
        pass


def measure_one() -> float:
    t0 = time.perf_counter()
    _get()
    return (time.perf_counter() - t0) * 1000.0  # ms


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    load_active = threading.Event()
    shutdown = threading.Event()

    def hammer():
        while not shutdown.is_set():
            if load_active.is_set():
                _get()
            else:
                time.sleep(0.02)

    threads = [threading.Thread(target=hammer, daemon=True) for _ in range(BURST)]
    for t in threads:
        t.start()

    for _ in range(8):  # warm up (schema generation, connection setup)
        measure_one()

    latencies = []
    for i in range(N):
        # Each 90-sample cycle has BOTH kinds of episode so the trace fairly
        # tests both behaviors:
        #   - a SUSTAINED load episode (35 samples) — genuine high load that
        #     warrants scale-up (a correct controller should respond)
        #   - a short TRANSIENT spike (2 samples) — measurement noise a stable
        #     controller should ignore
        cyc = i % 90
        sustained = 25 <= cyc < 60
        spike = 75 <= cyc < 77
        if sustained or spike:
            load_active.set()
        else:
            load_active.clear()
        latencies.append(round(measure_one(), 3))
        time.sleep(0.005)

    shutdown.set()

    s = sorted(latencies)
    p = lambda q: s[min(len(s) - 1, int(q * len(s)))]
    provenance = {
        "dataset": "measured",
        "source": "real",
        "measured": True,
        "url": URL,
        "n": len(latencies),
        "burst_concurrency": BURST,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "mapping": "NONE — measured wall-clock HTTP latency (ms); no M/M/1 model",
        "method": (
            "sequential GET latency with periodic N-way concurrency bursts to "
            "induce realistic tail latency on a live HTTP service"
        ),
        "p50_ms": round(p(0.50), 2),
        "p95_ms": round(p(0.95), 2),
        "max_ms": round(max(latencies), 2),
    }
    (OUT_DIR / "measured_latency.json").write_text(
        json.dumps({"latency": latencies, "provenance": provenance}, indent=2)
    )
    print(f"saved {len(latencies)} samples -> {OUT_DIR/'measured_latency.json'}")
    print(f"p50={provenance['p50_ms']}ms  p95={provenance['p95_ms']}ms  max={provenance['max_ms']}ms")


if __name__ == "__main__":
    main()
