#!/usr/bin/env bash
# Reproducible real-trace fetcher for CSA-ACI.
#   Wikipedia projectviews → downloaded automatically (small, public, no auth).
#   Google Borg 2019 / Azure → printed commands (need gsutil / git + accept terms).
# Usage:  scripts/fetch_traces.sh [YYYYMMDD]    (date defaults to 20260609)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
DATE="${1:-20260609}"
YEAR="${DATE:0:4}"; MONTH="${DATE:4:2}"

# ── 1. Wikipedia pageviews (REAL, automated) ──────────────────────────────────
WIKI="$RAW/wikipedia"
mkdir -p "$WIKI"
echo "==> Wikipedia projectviews for $DATE → $WIKI"
ok=0
for H in $(seq -w 0 23); do
  f="projectviews-${DATE}-${H}0000"
  url="https://dumps.wikimedia.org/other/pageviews/${YEAR}/${YEAR}-${MONTH}/${f}"
  if [ -s "$WIKI/$f" ]; then echo "    have   $f"; ok=$((ok+1)); continue; fi
  if curl -fsSL "$url" -o "$WIKI/$f"; then echo "    fetched $f"; ok=$((ok+1));
  else echo "    MISS   $f  ($url)"; rm -f "$WIKI/$f"; fi
done
echo "    -> $ok hourly files present"

# ── 2. Google Borg 2019 (REAL, manual — needs gsutil + dataset terms) ─────────
cat <<EOF

==> Google Cluster 2019 (manual): requires the gcloud/gsutil CLI.
    mkdir -p "$RAW/google/task_usage"
    gsutil -m cp gs://clusterdata_2019_a/task_usage/part-00000-of-00500.csv.gz "$RAW/google/task_usage/"
    # docs: https://github.com/google/cluster-data

==> Azure VM traces (manual, recommended 3rd dataset):
    git clone --depth 1 https://github.com/Azure/AzurePublicDataset "$RAW/azure/src"
    # place a per-VM CPU CSV into "$RAW/azure/", then add data/loaders/azure.py
    # (mirror google_cluster.py) and an "azure" entry in trace_loader.DATASETS.

Verify provenance after fetching:
    docker exec csa_backend python -c "from app.services.trace_loader import list_datasets; print(list_datasets())"
EOF
