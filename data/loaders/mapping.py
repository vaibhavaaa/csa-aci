"""
Latency mapping shared across trace loaders.

Resource pressure (CPU utilisation, or normalised request rate) is mapped to an
observed-latency signal using the M/M/1 mean response-time formula:

        R = S / (1 - rho)

where S is the unloaded service time (`base_ms`) and rho in [0, 1) is
utilisation. As rho -> 1 the queue saturates and latency diverges — exactly the
regime that should trigger SCALE_UP. This is a standard, citable queueing
approximation (Kleinrock, *Queueing Systems* Vol. 1).

Keeping the mapping in one place means Google (CPU) and Wikipedia (rate) traces
are converted to latency on identical, defensible terms.
"""
from __future__ import annotations

from typing import Iterable, List


def utilisation_to_latency(
    util: float,
    base_ms: float = 20.0,
    rho_cap: float = 0.99,
) -> float:
    """Map a single utilisation value in [0, 1] to a latency in ms."""
    rho = min(max(float(util), 0.0), rho_cap)
    return round(base_ms / (1.0 - rho), 2)


def series_to_latency(
    utils: Iterable[float],
    base_ms: float = 20.0,
    rho_cap: float = 0.99,
) -> List[float]:
    """Map a utilisation series to a latency series (ms)."""
    return [utilisation_to_latency(u, base_ms, rho_cap) for u in utils]
