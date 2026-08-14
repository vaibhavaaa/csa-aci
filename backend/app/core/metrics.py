"""
Domain Prometheus metrics.

The HTTP-level series (request latency/count/size) come from
prometheus-fastapi-instrumentator in app/main.py. This module holds the
CCE-specific series — the ones that describe governance health rather than
web-server health. Scraped at /metrics by the in-cluster Prometheus
(see infra/deployment/monitoring/).
"""

from prometheus_client import Counter

# A non-finite input (NaN / inf / None) reached the governor. The step is held
# at HOLD and reported as INVALID_INPUT rather than acted on or raised.
#
# Why this is a metric and not just a log line: the failure it detects is
# SILENT by nature. NaN telemetry makes every threshold comparison evaluate
# False, so both agents fall through to HOLD and the emergency branch never
# fires — the governor stops governing while the dashboard shows a calm system
# emitting HOLD. Without a counter the only symptom is an absence of action,
# which is indistinguishable from a healthy quiet period.
#
# Suggested alert: any sustained non-zero rate.
#   rate(csa_aci_invalid_input_total[5m]) > 0
CCE_INVALID_INPUT_TOTAL = Counter(
    "csa_aci_invalid_input_total",
    "CCE steps held at HOLD because an input was non-finite (NaN/inf/None).",
    ["field"],
)
